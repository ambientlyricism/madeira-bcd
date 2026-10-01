# Ghost of Tsushima: "No installed graphics card has been detected" (2026-10-01)

> **Türkçe özet:** 2026-09-28'de çalışan, 222'den (upstream'e geçiş) beri her
> açılışta "No installed graphics card ... monitor is connected to it" diyen
> GoT diyaloğunun kaynağı büyük olasılıkla win32u'daki sanal monitörün
> kimliği: 17088ab (upstream'in `sysparams_ios.c`'si) ile iki şey kayboldu —
> `GetMonitorInfo` monitöre Windows'un "bağlı değil" adı olan `"WinDisc"`
> diyor (eskiden `"\\.\DISPLAY1"`), ve `EnumDisplayDevices("\\.\DISPLAY1", 0,
> EDD_GET_DEVICE_INTERFACE_NAME)` monitör için BOŞ DeviceID dönüyor (eskiden
> `\\?\DISPLAY#Default_Monitor#...`). GoT tam bu çağrıyı yapıyor (loglarda
> `monitor idx=0 flags=0x1`). Eski cevaplar geri geldi (`MADEIRA_VMON_IDS=0`
> eskisini — upstream'i — geri getirir), oyunun kendi log satırları
> `[guest-log]` olarak yine session log'da, NVAPI cevapları `[nvapi]` olarak
> görünüyor. God of War bu çağrıları hiç yapmıyor (risk düşük).

## 1. What the game does before the dialog

The order is the same in every run (good or bad), only the answers differ.
From the 2026-09-26 19:58 log (`e8084388-...19-58-10.txt`, the run before the
NVAPI entry points existed, so DXMT's NVAPI printed each missing call):

| line | event |
|---|---|
| 9412 | `nvapi: function NvAPI_GetLogicalGPUFromPhysicalGPU not implemented` (NVAPI GPU enumeration) |
| 9590 | `[monitor-identity]` -- DXGI `EnumOutputs` / `GetDesc` |
| 9591 | `[vmode] synthesized EnumDisplayDevices adapter idx=0` -- `EnumDisplayDevices(NULL, 0)` |
| 9592-9595 | `NvAPI_GetAssociatedNvidiaDisplayHandle(<adapter name>)`, `NvAPI_GetAssociatedDisplayOutputId` |
| 9596 | `[vmode] synthesized EnumDisplayDevices monitor idx=0 flags=0x1` -- **`EnumDisplayDevices(L"\\.\DISPLAY1", 0, &dd, EDD_GET_DEVICE_INTERFACE_NAME)`** |
| 9597 | adapter again |
| 9602-9607 | probe device: `D3D12CreateDevice` -> `destroyed Device` |
| 9644-9651 | `[NxReflex]` Streamline results |
| 9661 | `[NxApp] Failed to get GPU Driver Info` |
| 9809 | dialog "No installed graphics card ... your monitor is connected to it correctly" |

So the game builds a display table -- adapter GDI name -> NVIDIA display
handle -> output id -> **monitor device interface path** -- and later looks
up the GPU's driver info for the adapter that drives a monitor. That run
already had the monitor's interface path (old win32u) and failed on the
missing NVAPI display handle ("[Render] Failed to get the nvidia display
handle"); once NVAPI answered (patch-dxmt-nvapi.py) and the registry had the
adapter, GoT went on. Each link of that chain is needed.

## 2. Good vs bad, up to the probe device

| | good 09-28 20:39 (`439d33b8`, IPA 218 + pack 5) | bad 09-28 20:41 (`6b7f7ce6`, same build) | bad 282 / 286 / 291 (`33d1bf01`, `e89af549`, `9bbf6144`) |
|---|---|---|---|
| vgpu registry | L4525 `[vgpu] registered ...10DE&DEV_2544 ... 35.0.15.6094` | L4527 same | L3887 / L3931 / L3931 same (286+: stale Apple adapter removed first) |
| DXGI output monitor | L9552 `using user32 primary=0x10001` | L9520 same | 282/286: synthetic sentinel; 291 L8894 `using user32 primary=0x10001` |
| EnumDisplayDevices calls | L9553-9555 adapter, monitor **flags=0x1**, adapter | L9521-9523 same | L8907-8909 / L8901-8903 / L8895-8897 same calls |
| monitor DeviceID returned | `\\?\DISPLAY#Default_Monitor#4&madeira&0&UID0#{E6F07B5F-...}` | same | **empty** (and DeviceKey empty) |
| GetMonitorInfo `szDevice` | `\\.\DISPLAY1` | same | **`WinDisc`** |
| DXGI mode list | L9560-9561 `[dxgi-modes] count=19` | L9528-9529 same | not logged (upstream made that log opt-in, `DXMT_DISPLAY_MODE_STATS=1`) |
| probe device | L9564-9569 | L9532-9537 | L8903-8907 (291) |
| game's own text log | L9582-9583 Reflex/DLSSG, then L9589 second device | L9550-9551, **L9556 `[NxApp] Failed to get GPU Driver Info`**, L9740 dialog | no `[guest-log]` at all (mirror gone), L9034 dialog (291) |
| video budget | 1536 MB | 1536 MB | 1536 MB |

The two "monitor" rows are not in the logs; they are what the code of each
build answers:

* good: `git show 6bbd6b8:build/win32u-unix/sysparams_ios.c`, L2735
  (`else if (monitor == &virtual_monitor) strcpy( buffer, "\\\\.\\DISPLAY1" )`,
  "iOS-Madeira 2026-09-16") and L4797-4830 (monitor DeviceID / DeviceKey).
* bad: 17088ab ("win32u: upstream's sysparams_ios.c with our GPU registration
  on top", 2026-09-29, the build 222-226 switch) replaced the file with
  upstream's and kept only our two commits; at HEAD before this change L2479
  `else strcpy( buffer, "WinDisc" )`, L4501 `else *info->DeviceID = 0;`, L4508
  `else *info->DeviceKey = 0;`.

Everything else the game can observe before the dialog is the same code in
both pins or ruled out:

* DXGI: `dxmt/src/dxgi` is identical between the old pin (125hz `462a77e`) and
  `a5e0cd3` except the opt-in mode log; `wsi_monitor_headless.cpp` differs
  only in the monitor-identity / mode-table switches (fixed in 291).
* NVAPI: `dxmt/src/nvapi` identical; the NUL fix (291) is the only change.
* madeira-d3d12, pack 5 (69d7311) vs HEAD: the probe touches nothing that
  changed (no `CheckFeatureSupport` in the probe -- the new
  `[d3d12-caps] ml1970` line never prints in 291; the diff is F0 quieting,
  one-pass conversion, root-signature deserializers, the opt-in typed UAV
  load flag).
* winemetal unix: only per-caller switches for 32-bit callers.
* wine (125hz `c9c186e` vs willfaust `4f5b197`): win32u `d3dkmt.c` identical;
  ntdll/unix differences are WoW64 plumbing -- plus the lost `[guest-log]`
  mirror in `file.c`.
* PE DLLs the game loads: `user32`, `gdi32`, `win32u`, `setupapi`,
  `kernelbase` identical (same module ids in both logs); `dxgi`, `winemetal`,
  `nvapi64`, `d3d12`, `ntdll` differ (see above).
* registry: `write_gpu_to_registry` / `ios_register_virtual_gpu` unchanged
  except the stale-adapter cleanup (286).
* DisplayConfig: `QueryDisplayConfig` reports no path for the source-less
  virtual monitor in both (f2bcaeb), `D3DKMTEnumAdapters2` lists no GPU in
  both -- not the regression, but now logged.

## 3. Root cause, ranked

1. **(Most likely; fixed here.) The virtual monitor lost its Win32 identity
   in 17088ab.** GoT asks `EnumDisplayDevices(L"\\.\DISPLAY1", 0,
   EDD_GET_DEVICE_INTERFACE_NAME)` for the monitor's device interface path --
   the key of its display table -- and gets an empty string; and
   `GetMonitorInfo` names the monitor `"WinDisc"`, which is what Windows
   calls a *disconnected* display, so nothing matches the DXGI output's /
   EnumDisplayDevices' `"\\.\DISPLAY1"`. The dialog's own text ("...your
   monitor is connected to it correctly") is exactly that failure. GoT was
   not launched between 09-28 and 10-01, so the regression stayed hidden.
2. **(Same cause, NVAPI side; fixed here.)** DXMT's
   `NvAPI_DISP_GetDisplayIdByDisplayName` compares the name with
   `GetMonitorInfo`'s `szDevice` only, so with `"WinDisc"` a game asking by
   `"\\.\DISPLAY1"` got `NVAPI_NVIDIA_DEVICE_NOT_FOUND`. (Our own
   `NvAPI_GetAssociatedNvidiaDisplayHandle` already fell back to the primary.)
3. **(Explains the intermittent 09-28 20:41 failure; fixed in 291.)** NVAPI
   strings without NUL (`7a28d1e`): the driver branch string carried stack
   garbage, so "GPU Driver Info" could fail run to run on the old build too.
4. **(Open, not a regression.)** Inconsistencies that were the same in the
   good run: NVAPI says "NVIDIA GeForce RTX 4090", driver 999.99, PCI device
   id 0 (`0x000010DE`) while DXGI / the registry say RTX 3060 `10DE:2544`,
   driver 35.0.15.6094; no DisplayConfig path for the monitor; D3DKMT lists
   no adapter. If the dialog survives this change, these are next -- the new
   `[nvapi]`, `[vdcfg]`, `[vkmt]` and `[guest-log]` lines say which one.

## 4. What changed (this branch)

* `build/win32u-unix/sysparams_ios.c`
  * `GetMonitorInfo` (`monitor_get_info`): the virtual monitor is
    `"\\.\DISPLAY1"` again, not `"WinDisc"`.
  * `NtUserEnumDisplayDevices` (synthesized branch): the monitor under
    `"\\.\DISPLAY1"` gets the pre-222 ids again -- DeviceID
    `\\?\DISPLAY#Default_Monitor#4&madeira&0&UID0#{E6F07B5F-EE97-4A90-B076-33F57BF4EAA7}`
    with `EDD_GET_DEVICE_INTERFACE_NAME`, `MONITOR\Default_Monitor\{4D36E96E-...}\0000`
    without, DeviceKey `...\Control\Class\{4D36E96E-...}\0000`. The adapter
    is unchanged (PCI id, `Video\{8C0C2A5B-...}\0000`, no interface name).
  * `MADEIRA_VMON_IDS=0` restores upstream's answers (both of the above).
  * Diagnostics (a few lines per session): `[vmon] GetMonitorInfo(EX) ...
    szDevice=`, `[vmode] synthesized EnumDisplayDevices ... flags= cb= id=
    key=` (first 8), `[vmode] EnumDisplayDevices refused device=...` (a name
    we never handed out), `[vdcfg] GetDisplayConfigBufferSizes /
    QueryDisplayConfig / DisplayConfigGetDeviceInfo type= id= -> status`,
    `[vkmt] D3DKMTEnumAdapters2 -> status, N adapters`.
* `tools/patch-wine-guest-log.py` (CI step "Patch wine with the game
  text-log mirror", before "Build ntdll-unix"): the `[guest-log]` mirror is
  back in `wine/dlls/ntdll/unix/file.c` `NtWriteFile`. Default: lines of
  `*.log` / `output_log.txt` writes containing error / fail / exception /
  unsupported / gpu / driver / adapter / graphics / monitor / display /
  nvapi / nvidia, 64 lines per session, each file named once (`[guest-log]
  file <path>`). `MADEIRA_GUEST_LOG=all` mirrors every line (400),
  `MADEIRA_GUEST_LOG=0` (or the old `MADEIRA_GUEST_LOG_ERRORS=0`) turns it
  off, `MADEIRA_GUEST_LOG_LIMIT=N`. Binary writes cost one byte scan; the
  path is asked only for a kept line.
* `tools/patch-nvapi-trace.py` (run by `tools/build-dxmt-nvapi.sh`):
  * the `[nvapi] query 0x... NvAPI_X` trace goes through DXMT's Logger
    (`__wine_dbg_output`); the old `fprintf(stderr)` never reached the log;
  * 30 adapter / display / driver entry points answer through a logging
    wrapper, `[nvapi] NvAPI_X -> <status>` (first 6 calls and later
    failures; details for display name / id, driver version and branch, GPU
    count, LUID, full name). Status: 0 OK, -3 no implementation, -5 invalid
    argument, -6 NVIDIA device not found, -7 end of enumeration, -9 struct
    version, -101 expected GPU handle, -104 not supported. Per-frame entry
    points (latency, sleep, UAV overlap) are not wrapped;
  * `NvAPI_DISP_GetDisplayIdByDisplayName` answers the primary display id
    for the primary adapter's EnumDisplayDevices name when the
    `GetMonitorInfo` match fails (logged "primary adapter name").
  NVAPI loads only with "Report an NVIDIA GPU" (`DXMT_ENABLE_NVEXT=1`).
* Host checks: `tests/host/check-vmon-identity.py`,
  `tests/host/check-guest-log.py` (with `WINE_SRC=` also against the real
  `file.c`), `tests/host/check-nvapi-trace.py` (with `DXMT_SRC=` and an
  arm64ec llvm-mingw in `MINGW=` it compiles nvapi.cpp and checks every
  wrapper has an x64-callable entry thunk). Also checked here, not in a
  script: `sysparams_ios.c` and the patched `file.c` pass `clang
  -fsyntax-only -Wall` with `WINE_IOS` against the wine pin's (host
  configured) headers with no new warning, and `nvapi64.dll` links for
  arm64ec with llvm-mingw 20260421 exactly as `tools/build-dxmt-nvapi.sh`
  builds it.

## 5. God of War

GoW's logs (09-29 .. 10-01, builds 226-279) have no `[vmode] synthesized
EnumDisplayDevices` and no `[iOS ChangeDisplaySettings]` line: it never asks
for display devices or changes the mode, and it runs with NVIDIA reporting
off, so NVAPI never loads. What it can still see is `GetMonitorInfo`'s
`szDevice`, which is now the name every other API already used -- the value
it had in every build up to 221. The `[guest-log]` mirror ran in every build
up to 221 too. Risk: low; `MADEIRA_VMON_IDS=0` / `MADEIRA_GUEST_LOG=0` in
GoW's game file undo either.

## 6. What to test and which lines to send

GoT with "Report an NVIDIA GPU" on, fresh launch, then the whole session log.
Expected, in order:

* `[vmon] GetMonitorInfo(EX) monitor=0x10001 szDevice=\\.\DISPLAY1 ...`
* `[vmode] synthesized EnumDisplayDevices monitor idx=0 flags=0x1 ... id=\\?\DISPLAY#Default_Monitor#...`
* `[nvapi] query 0x... NvAPI_...` (the full list GoT asks for) and
  `[nvapi] NvAPI_... -> 0` lines; any non-zero status before the dialog is
  the next lead.
* `[guest-log] file /var/mobile/.../Documents/wine/drive_c/.../<name>.log`
  (the unix path of the game's log, so the whole file can be fetched from
  the Files app) and `[guest-log] #N ... [NxApp] ...` -- the game's own
  reason if it still refuses.
* then the second `D3D12CreateDevice` and the launcher window; no
  `[win-name] ... "No installed graphics card ..."`.

If the dialog is still there: send the log, and with `env.MADEIRA_GUEST_LOG =
all` in GoT's game file one more (every line of the game's log up to the
dialog). `[vdcfg]` / `[vkmt]` lines show whether it queried DisplayConfig or
D3DKMT for the adapter.
