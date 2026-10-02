# GTA V Enhanced: the child process dies at its first x64 syscall

> **Türkçe özet:** GTA V Enhanced çocuk süreç (pseudo-process) olarak
> başlatılınca ilk x64 `syscall`'unda ölüyordu. Sebep: her x64 süreç kendi
> emülatörünü (libarm64ecfex.dll / xtajit64) yüklüyor; çocuk sürecin kendi
> ntdll kopyası var, ama emülatörün takma ad (alias) tablosuna yalnızca ana
> sürecin ntdll kopyası yazılıyordu. Syscall dönüşü ntdll'in x64 yardımcısına
> (`invoke_arm64ec_syscall`, ntdll+0x87050) çocuğun KENDİ kopyasındaki adresten
> gidiyor; FEX bu adresi PE adresine çeviremedi ("NoExec") ve süreç erişim
> ihlaliyle kapandı. Ana süreçte aynı yol `[pool-rip-fix]` ile çalışıyor.
> Düzeltme (yalnız Wine tarafı, FEX'e dokunulmadı): çocuğun emülatörü artık
> çocuğun kendi ntdll kopyasını alıyor. Ana süreçler (God of War, Ghost of
> Tsushima) için hiçbir şey değişmiyor. Kapatma anahtarı:
> `env.MADEIRA_CHILD_OWN_NTDLL = 0`.

Logs: build 291, PlayGTAV.exe 2026-10-01 18:37:52 (PlayGTAV main, GTA5_Enhanced
child) and GTA5_Enhanced.exe 18:38:27 (GTA5 main, PlayGTAV child); for
comparison build 286 (17:31:38 / 17:32:19) and Ghost of Tsushima 2026-09-26..28.

## 1. What happens

1. A pseudo-process child is a thread group in the same iOS process with its
   own PEB/TEB. It gets a **private copy of ntdll** in the JIT pool
   (`ios_jit_copy_module_for_child`, mapping entry with `owner_peb` = the child;
   `[child-ntdll] copied 0x71ffcd0000+0x130000 -> 0x14fba8000 ... owner_peb=0x10999c000`).
   Every other module is mapped by the child itself at its own VA.
2. Every x64 process, child or not, **loads its own emulator**:
   libarm64ecfex.dll (shipped as xtajit64.dll) at its own VA, with its own pool
   copy and therefore its own `IosAliasEntries` table (FEX
   `Source/Windows/ARM64EC/IosJitAlias.cpp`). Main: `libarm64ecfex.dll` at
   0x71fe8c0000 -> pool 0x148518000; child: 0x71fcdb0000 -> pool 0x14fce0000.
   The two FEX range trackers differ too (`tracker=0x1488dcb78` vs `0x1500a4b78`).
3. When an emulator starts, PE ntdll's `arm64ec_process_init_dispatchers`
   calls `unix_ios_push_jit_aliases`, and the unix side
   (`unixcall_ios_push_jit_aliases`, virtual_ios.c) drains the JIT mapping
   table into that emulator's alias table. **The drain skipped every
   owner-tagged entry** ("x86-64 children under FEX will need per-process alias
   routing -- deferred to S3"), so a child's emulator mapped ntdll to the
   PARENT's copy and knew nothing about the child's own copy.
4. An x64 `syscall` / `int 2e` in emulated code (here: RUNE64.dll calling
   ntdll's x64 stub of NtProtectVirtualMemory -- `rax=0x50`,
   `R10=0x71ffd55a17` = the stub's return point at ntdll+0x85a17, return
   address RUNE64+0x40903f on the stack) goes FEX `ECSyscallHandler::HandleSyscall` ->
   `STATUS_EMULATION_SYSCALL` -> ntdll `prepare_exception_arm64ec` ->
   `dispatch_syscall` (wine `dlls/ntdll/signal_arm64ec.c`), which sets
   `context->Pc = invoke_arm64ec_syscall` and resumes emulation.
   `invoke_arm64ec_syscall` is x64 code at **ntdll+0x87050**
   (`mov [rsp+8],r10; pop r10; mov [rsp+8],r10; lea r10,arm64ec_syscalls; call [r10+rax*8]; ...`,
   wine `dlls/ntdll/signal_x86_64.c`). `dispatch_syscall` is EC code running
   from the process's pool copy, so the address it takes is the **pool alias**
   of that helper: main copy 0x1483e0000 + 0x87050 = 0x148467050, child copy
   0x14fba8000 + 0x87050 = 0x14fc2f050.
5. FEX `CompileBlock` (FEXCore Core.cpp, ml315 `[pool-rip-fix]`) turns a guest
   RIP inside a module pool copy back into its PE VA with
   `IosJitReverseTranslate` -- a lookup in the emulator's own alias table -- and
   re-enters the dispatcher. In the main process the table has the main's copy:
   `[pool-rip-fix] #1 guest RIP 0x148467050 is a module POOL-COPY alias of PE 0x71ffd57050`.
   In the child the table does not have the child's copy, so the lookup
   returns the address unchanged, the range tracker does not know it either,
   and the frontend refuses the block: `NoExec instruction in entry block`.
6. `NoExecOp` emits a `Break` with `FAULT_SIGSEGV`, which jumps to FEX's
   `GuestSignal_SIGSEGV` dispatcher trampoline. That trampoline spills the
   static registers into the thread state and then **deliberately** loads from
   address 0 to raise the signal (Dispatcher.cpp, "Force a SIGSEGV by loading
   zero"). The fault is converted into a guest access violation at the pool
   RIP, dispatched to RUNE64.dll's handler, the unwind walks into garbage
   ("Exception frame is not in stack limits") and the process ends with
   0xC0000005.

The same happens to any x64 child that executes an x64 syscall stub. It is
not GTA-specific: crs-handler.exe (Ghost of Tsushima's crash handler, a child)
died the same way in the 2026-09-26..28 logs (ntdll layout then had the helper
at +0x88050).

## 2. Evidence

PlayGTAV.exe-2026-10-01_18-37-52 (build 291; main PlayGTAV peb 0x71ffff0000,
tid 0024; child GTA5_Enhanced peb 0x10999c000, tid 002c):

| line | what |
|---|---|
| 426, 569 | main emulator: `libarm64ecfex.dll` 0x71fe8c0000 -> pool 0x148518000; `[hold-release] ml618 registered peb=0x71ffff0000` (its `arm64ec_process_init_dispatchers`, same function as the alias push) |
| 1249-1470 | main, tid 24: `[pool-rip-fix] #1..#24 guest RIP 0x148467050 ... alias of PE 0x71ffd57050` -- the main survives its x64 syscalls |
| 1613-1614 | `NtCreateUserProcess` GTA5_Enhanced.exe, `[phase] spawn` t+4.469 s |
| 1660-1668 | `[child-ntdll]` DIR64 fixups, x18 patch, `copied 0x71ffcd0000+0x130000 -> 0x14fba8000 ... owner_peb=0x10999c000` |
| 1698 | child emulator: `libarm64ecfex.dll` 0x71fcdb0000 -> pool 0x14fce0000 (a second, separate FEX) |
| 1807 | `[hold-release] ml618 registered peb=0x10999c000 cb=0x14fdf290c` -- the child's emulator registered (cb is inside the child's FEX copy) |
| 1853-1854 | the child's tracker 0x1500a4b78 knows ntdll's PE executable sections (0x71ffce0000-0x71ffd570a5): the PE VA would have compiled |
| 2897-2900 | `[iOS-xquery] MISS tracker=0x1500a4b78 addr=0x14fc2f050 rev=0x14fc2f050` (twice), `NoExec instruction in entry block: 14FC2F050`, `[iOS-noexec] status=NOEXEC ... repeat=1` |
| 2907 | `[rip-leak] guest RIP 0x14fc2f050 IS POOL addr = PE 0x71ffd57050 (module base 0x71ffcd0000 rva 0x87050)` -- the unix-side table knows the child copy; only the emulator does not |
| 3049-3085 | `segv_handler SEGV ... pc=0x169ff8660 addr=0x0`, `[guest-state] rip=0x14fc2f050`, `[emit-dump]` (decoded below) |
| 3090 | `[exc-disp] raise tid=002c code=c0000005 ... p0=0 p1=0` |
| 3111, 3121 | handler `RUNE64.dll+0x456d10`; `Exception frame is not in stack limits` |
| 3122 | `NtTerminateProcess(..., exit_code=0xc0000005)` |

GTA5_Enhanced.exe-2026-10-01_18-38-27 (build 291; main GTA5 tid 0024, child
**PlayGTAV.exe** peb 0x10a208000, tid 002c). Correction to the earlier reading:
tid 002c here is the PlayGTAV.exe child, not a GTA5 grandchild -- PlayGTAV dies
before it can start one (only one `NtCreateUserProcess`, line 1945):

| line | what |
|---|---|
| 1764-1811 | main: `[pool-rip-fix] #1..#24 guest RIP 0x14dc13050 -> PE 0x71ffd57050` |
| 1945, 1995 | spawn PlayGTAV.exe; `[child-ntdll] copied ... -> 0x152610000 owner_peb=0x10a208000` |
| 2015-2222 | main exits with 0x1337; the build 291 session wait keeps the session for playgtav.exe |
| 2234, 2320 | child emulator 0x71fa3e0000 -> pool 0x152748000; registered peb=0x10a208000 |
| 2897-2899, 2907 | `[iOS-xquery] MISS ... addr=0x152697050` (= 0x152610000 + 0x87050), `NoExec`, `[rip-leak] ... rva 0x87050` |
| 3097 | PlayGTAV `NtTerminateProcess(..., 0xc0000005)`; 6725-6729 last child exits, wineserver stops |

Ghost of Tsushima 2026-09-28 18:56:19: main `[pool-rip-fix] #1 guest RIP
0x12287c050 ... PE 0x70ffd58050` (line 9336); crs-handler.exe child (tid 0050,
peb 0x1173e8000, copy 0x12b244000): `NoExec instruction in entry block:
12B2CC050` (50993), `[rip-leak] ... rva 0x88050` (51000), then
`MADEIRA-EXIT: crs-handler.exe` (51099). Same in 09-26 23:28:48 (56613/56617).
The 2026-10-01 GoW/GoT logs have no NoExec at all: crs-handler did not execute
an x64 syscall stub in those sessions.

### The emit dump at the fault (PlayGTAV log line 3079-3085)

```
-48  stp x25,x26,[x28,#80]   stp x2,x3,[x28,#96]   stp x4,x5,[x28,#112]
     stp x19,x20,[x28,#128]  stp x21,x22,[x28,#144] stp w9,w24,[x28,#16]
-24  add x10,x28,#448        st1 {v0-v3},[x10],#64 ... st1 {v12-v15},[x10],#64
     mov w1,#0
 +0  ldr x1,[x1]             <- fault, x1 = 0
 +4  mrs x10,fpcr; and x10,x10,#~7; msr fpcr,x10; mrs x10,nzcv; str w10,[x28,#1032]; ...
```

x28 = 0x7c0a001140 is FEX's CpuStateFrame (`[vname]` shows the thread-state
arena). The block before the fault is `SpillStaticRegs` into it; then
`LoadConstant(x1, 0); ldr x1,[x1]`. The null pointer is not a structure: it is
FEX's `GuestSignal_SIGSEGV` trampoline raising a SIGSEGV on purpose. What
follows (+4 on) is the next dispatcher stub's prologue, not reached. The guest
side of the fault is therefore the NoExec at 0x14fc2f050, not a data access.

## 3. Fix (build/ntdll-unix, no FEX change)

* `unixcall_ios_push_jit_aliases` (virtual_ios.c): the process that registers
  its emulator (`ios_jit_current_peb()` on the calling thread) now gets **its
  own copy** of an image when it has one, instead of the parent's
  (`ios_jit_alias_drain_wants` / `ios_jit_owned_copy`; a tombstoned copy, size
  0, never counts). FEX keeps one entry per PE range, so exactly one of the two
  is pushed. Effects in a child's emulator:
  - `IosJitReverseTranslate(child copy + x)` = PE + x, so `[pool-rip-fix]`,
    `QueryGuestExecutableRange` and the exception path (`[exc-pool-rip]`) work
    for the child exactly as they do for the main process;
  - `ExitFunctionEC` (x64 -> EC calls into ntdll) enters the child's own copy
    instead of the parent's -- what the owner-aware `ios_jit_translate_addr`
    and the Mach exec-fault redirect already did. Before, a child's x64 code
    calling an ntdll EC export ran the parent's copy, with the parent's
    `.data` (loader lists, locks).
  - A main process owns no copies: its drain is byte-for-byte the old one.
  - `MADEIRA_CHILD_OWN_NTDLL=0` (env, or `env.MADEIRA_CHILD_OWN_NTDLL = 0` in
    a game file) restores the old drain. In Settings > All settings under
    Memory & JIT pool.
* `ios_patch_rtl_pc_to_file_header_current` + its call in
  `wine_ios_child_main` (loader_ios.c): a child's private ntdll copy now also
  gets the RtlPcToFileHeader pool-alias patch that the session's copy gets in
  `load_ntdll_functions` (Ghost of Tsushima's C++-exception fix). Needed
  because a child's x64 calls into ntdll now land in the child's copy.
* `ios_jit_reclaim_process`: if the dying pseudo-process is the one whose
  emulator holds the alias-push callback, the callback is dropped before the
  pool copy is reclaimed (it used to dangle: the next image map anywhere would
  call freed, later reused code). The next emulator to register gets the
  whole table from its drain anyway.
* Diagnostics (`[alias-push] madeira-bcd ...`, see section 5).

Why not in FEX: the fix is a question of what the unix side tells each
emulator, and it fits the existing one-callback ABI (the struct shared with the
prebuilt PE ntdll stays one field). A FEX change would have to go through
`tools/build-xtajit64.sh`, which rebuilds the ARM64EC module and checks it
against the committed xtajit64.dll by fingerprint. Note for future FEX patches:
the FEX build caches in .github/workflows/build-ipa.yml are keyed by the FEX
submodule SHA only (`fex-ios-<sha>-v3`, `fex-arm64ec-<sha>-v2`,
`fex-wow64-<sha>-v1`); the tools/patch-fex-*.py scripts are not part of the
key, so a new patch needs a key bump or it is skipped on a cache hit (the
iOS patch steps are `if: steps.fexcache.outputs.cache-hit != 'true'`).

Host check: `python3 tests/host/check-child-ntdll-alias.py` compiles the
production functions against a model of FEX's alias table (one table per
emulator) and replays the build 291 layout: main unchanged; child reverse-
translates 0x14fc2f050 to 0x71ffd57050; `MADEIRA_CHILD_OWN_NTDLL=0` reproduces
the miss; dead copies ignored; cross-process line; callback drop; pc2fh aimed
at the shared image. PASS (with ASan/UBSan). The full files are only compiled
by CI (iOS SDK).

## 4. Risk

* Main processes (God of War, Ghost of Tsushima, Crysis): no change in what
  their emulator gets. New log lines only: one `[alias-push] ... registered
  its emulator` line per emulator, and up to 16 `[alias-push] ... image ...
  went to the emulator of peb=...` lines once a child has registered.
* crs-handler.exe (GoW/GoT child): its emulator now maps ntdll to its own copy
  (more correct; its x64 syscalls stop killing it). The game does not depend
  on crs-handler; if anything around it looks different, the switch above
  turns it back.
* GTA V: the child now gets past its first x64 syscall. What comes after
  (D3D12, DirectStorage, the game's own checks) has never run on this setup.

## 5. Next device log: what to look for

Start GTA V Enhanced either way (PlayGTAV.exe or GTA5_Enhanced.exe) and send
the whole log. Expected:

* For each emulator: `[alias-push] madeira-bcd peb=0x71ffff0000 registered its
  emulator ...: N mapping(s) pushed, 0 own copy(ies), 0 parent copy(ies) left
  out` (main), and for the child
  `[alias-push] madeira-bcd peb=0x...: not pushing the parent copy 0x... of 0x71ffcd0000+0x130000`,
  `[alias-push] madeira-bcd peb=0x...: emulator maps ntdll.dll 0x71ffcd0000+0x130000 to this process's own copy 0x...`
  (the address of `[child-ntdll] copied ... -> 0x...`) and its summary with
  `1 own copy(ies), 1 parent copy(ies) left out`.
* A second `[pc2fh] RtlPcToFileHeader 0x71ffd05aac (pool 0x...) now maps
  JIT-pool aliases ...` with the child's copy as the pool address.
* In the child's tid: `E 2C [pool-rip-fix] #1 guest RIP <child copy + 0x87050>
  is a module POOL-COPY alias of PE 0x71ffd57050` (each emulator counts its
  own #1..#24) and **no** `NoExec instruction in entry block` /
  `[iOS-noexec]` / `[iOS-xquery] MISS` for that address.
* `[alias-push] madeira-bcd image ... mapped by peb=A went to the emulator of
  peb=B` names images a process maps while another process's emulator holds
  the push callback (pre-existing, not fixed: see below). If GTA5 itself
  starts a helper process, its later DLLs (d3d12, DSTORAGE, ...) would show up
  here -- that would be the next thing to fix.
* `[alias-push] madeira-bcd peb=... exits while its emulator receives the
  alias pushes ... callback dropped` when such a process exits.
* If the child still dies: the first `[exc-disp] raise tid=<child>` /
  `segv_handler` / `NoExec` after `NtCreateUserProcess`, and the `[WineProc]`
  lines at the end.

## 6. Found on the way, not fixed

* **The alias-push callback is global.** `ios_jit_alias_pushback_cb` is
  replaced by every emulator that registers, so after a child starts, images
  the main process maps are pushed into the child's emulator, not its own.
  God of War 2026-10-01 15:52:42: crs-handler.exe registers at line ~2577;
  afterwards GoW maps secur32 (4757), mmdevapi, XAudio2_9, mfplat, propsys,
  rtworkq, mfreadwrite (8586-8784) and DSOUND (9111), all of which went to
  crs-handler's emulator. In GoW's own emulator `ExitFunctionEC` cannot
  translate them, so each x64 -> EC call into those DLLs takes the Mach
  exec-fault redirect (~33 us each), and a pool-copy RIP there could not be
  `[pool-rip-fix]`ed. Possible fix: a per-PEB callback table (route a push to
  the mapping process's emulator, fall back to today's rule for a process
  without one). It changes what GoW's emulator gets, so it was left for a
  decision; the new `[alias-push] ... went to the emulator of` lines measure it.
* **FEX never forgets a dead process's JIT ranges.** Its table retires entries
  by PE overlap only, and the reverse walk is oldest-first. When a child dies
  and its pool ranges are reused, an emulator that holds entries for them
  (images pushed to it while it was the registrant) can reverse-translate the
  new copy to the dead image's PE VA. Not observed yet.

## 7. Build 296: the child runs; the game stops at ERR_GFX_D3D_NOD3D12

> **Türkçe özet:** Çocuk süreç düzeltmesi cihazda çalıştı (build 296). Oyun
> artık çok daha ileri gidiyor ve kendi isteğiyle duruyor: 0x80000003, oyunun
> kendi ölümcül hata yolundaki `int3`. Hata kodu kayıtta görünüyor: RSI =
> 0x17b133bd = joaat("ERR_GFX_D3D_NOD3D12"), yani "DirectX 12 ekran kartı
> bulunamadı". Oyun Streamline'ı kurduktan sonra DXGI fabrikasını yeniden
> açıyor ve D3D12CreateDevice'ı hiç çağırmadan bu hataya gidiyor; yani bir
> adaptör/çıkış kontrolünü geçemiyor. Oyunun kendi imajına yazmaları doğru
> işleniyor. Madeira tarafında bulunup düzeltilen fark: çocuk süreçte
> GetDesktopWindow() hep NULL dönüyordu (masaüstü penceresi sınıfı yalnızca
> ilk sürece kayıtlıydı). Bir sonraki cihaz kaydı için oyunun dosyasına
> `env.MADEIRA_GUEST_LOG = all` (oyunun kendi crashcontext.log'u tamamen
> gelsin); hâlâ olmazsa ek olarak `env.DXMT_WSI_MONITOR_IDENTITY = 1` ve
> `env.DXMT_WSI_MODE_TABLE = 1` (Ghost of Tsushima'daki "ekran kartı yok"
> sorununun aynısı olabilir).

Logs: PlayGTAV.exe 2026-10-01 19:53:36 (PlayGTAV main -> GTA5_Enhanced child,
peb 0x10592c000) and GTA5_Enhanced.exe 19:54:23 (GTA5 main -> PlayGTAV child
-> GTA5 grandchild, peb 0x11c59c000). Line numbers below are the first log's.

### 7.1 The child-ntdll fix works

`[alias-push] ... emulator maps ntdll.dll 0x71ffcd0000+0x130000 to this
process's own copy 0x14fba8000` (1783), the child's `[pool-rip-fix] #1..#24
guest RIP 0x14fc2f050 ... PE 0x71ffd57050` (2885-2930), a second `[pc2fh]`
line for the child's copy, no NoExec; both start paths reach the game.

### 7.2 What raised 0x80000003

The game's own `int3` at GTA5_Enhanced.exe RVA 0x100798 (`[int3-guest]
guest_rip=0x140100799`, 6734; FEX turns it into `brk #0`, wine first reports
c000001d at the JIT pc, FEX rebuilds it as `80000003 addr=0000000140100798`,
6799-6803 -- the Windows shape, the address of the int3). The bytes after it
are `mov rax,[rip+...]; test rax,rax; je ...` (a fatal-error hook).

* First int3 (RSP 0x7070e2ee00): handled by the game's own handler
  GTA5_Enhanced.exe+0x2479e30, execution continues at RVA 0x15b8ed6 (6768-6770).
* Second int3, same RIP (RSP 0x7070e2ee70): no handler up to the root
  (`[unwind-root] ml633 ACCEPTING terminal root frame`, 6804); the game's
  unhandled-exception filter runs: thread 003c writes a minidump (refused by
  `[minidump-gate]`, 6822) and crashcontext.log (6895-6897), connects to port
  443 to send the report, and the process ends with `NtTerminateProcess(...,
  0x80000003)` (7114). There are no `[unwind-why]` / invalid-frame lines, so no
  frame was skipped: this is the game's decision, not an unwinding failure.
* **Which error:** RSI = 0x17b133bd at all four int3s in both logs (6736, 6780;
  second log 8398, 8442). That is Rockstar's string hash (joaat, lower-case) of
  `ERR_GFX_D3D_NOD3D12`, the D3D12 counterpart of the legacy edition's
  ERR_GFX_D3D_NOD3D11 ("DirectX 11 adapter or runner not found"). Neighbouring
  labels do not match: ERR_GFX_D3D_INIT 0x9cf7bd06, ERR_GFX_D3D_NOD3D11
  0x24c04ddb, ERR_GFX_D3D_NOFEATURELEVEL 0x2bcec5fa.

### 7.3 Where in start-up it gives up

* Thread 0054 (a hardware-info worker: WMI via wbemprox fails, 4526-4529)
  loads D3D12/winemetal/DXGI and creates a device on the default adapter at
  FL 12_0 (4654-4677) -- fine -- and destroys it.
* The game thread 0034: self-modifying writes into its own image (7.4), then
  D3D12/DXGI (5322-5383): factory, `IDXGIFactory7` not supported
  (`DXGIFactory: Unknown interface query a4966eed-...`; DXMT implements up to
  IDXGIFactory6), three `get_desktop_window ... top_window stays 0`,
  `[display] virtual monitor 1280x720`, `[vgpu] registered
  PCI\VEN_106B&DEV_0001` (Apple; "Report an NVIDIA GPU" is off for this game)
  -- no abort yet.
* Streamline: sl.interposer (5773), WinVerifyTrust on its plugins
  (`CryptDecodeObjectEx Unsupported decoder for 1.3.6.1.4.1.311.2.1.4`,
  SPC_INDIRECT_DATA -- the plugins load anyway), nvapi64 six times with
  `NvAPI_Initialize -> -6` (NVIDIA_DEVICE_NOT_FOUND, expected without NVIDIA
  reporting), sl.common, `[vkmt] D3DKMTEnumAdapters2 -> 0, 0 adapters` (6304),
  `vulkan_init_once Wine was built without Vulkan support`, sl.dlss, sl.dlss_g,
  sl.pcl, sl.reflex.
* Then D3D12/DXGI a last time (6699-6727): factory (IDXGIFactory7 again), three
  more `top_window stays 0`, and the int3 (6732). **No D3D12CreateDevice is
  logged after the probe on 0054** (madeira-d3d12 logs every call, probe or
  create), so the game rejected the adapter(s) during DXGI enumeration, before
  it asked D3D12 anything.

### 7.4 The self-writes into the read-only image are handled correctly

`[fault_rip] ... addr=0x140265bd5 kr=2(PROTECTION_FAILURE)` (4983/5081) and
`addr=0x14122be51` (5191/5229): the anti-tamper patches its own .text. FEX's
self-modifying-code path handles both: `Handled self-modifying code: pc:
16DA4E61C fault: 140265BD5` and `[smc-atomic] ml657 #1 handled` (5182-5184);
the next fault reports `previous SMC store at 0x140265bd0 ... changed the bytes
(store landed)` with the new bytes (5260-5262); the second store is retried
(`[smc-byte] ml1018 #1 DECLINED backpatch ... retrying at the same pc`, 5273)
and never faults again. The `[exc-disp] raise ... c0000005` lines (5173, 5264)
are this internal SMC round trip, not guest exceptions. Also seen and
survived: RUNE64's `We don't support modifying GS/FS selector in 64bit mode!`
and `IRET only implemented for 64bit and 32bit sizes` (FEX warnings about the
anti-tamper's probes).

### 7.5 Madeira-side difference found and fixed: no desktop window in a child

`get_desktop_window ... top_window stays 0` appears 9 times in each GTA log,
always on the game thread, and never in a God of War or Ghost of Tsushima log.
Cause: win32u's `init_user` (class_ios.c, `pthread_once`) runs only for the
session's first pseudo-process: only that process connects to the window
station and registers the desktop (#32769) and "Message" window classes. The
wineserver keeps classes per process and creates a missing desktop window in
the context of the process that asks (get_desktop_window with force, or the
first top-level CreateWindowEx). GoW/GoT create it from their main process.
GTA's main process is a launcher that never opens a window, so the shared
desktop has none and the child cannot create it -- GetDesktopWindow() returns
NULL for the rest of the run, and with it GetDC(NULL), GetWindowRect(desktop),
the child's first top-level CreateWindowEx (its game window) and whatever the
adapter/monitor check derives from them. register_builtin_classes() was made
per-process earlier for the same reason (Steam's update UI).

Fix (build/win32u-unix/winstation_ios.c `ios_child_desktop_fixup`; class_ios.c
publishes the session PEB at the end of init_user): when the server gives a
thread no desktop window and the process is not the session's own, once per
process: register the desktop/message classes for this process and ask again;
if the thread has no desktop at all, run winstation_init for this process (what
init_user did for the session) and ask once more. The server detaches the
desktop window from its creator at once (and releases the class), so it
outlives the child. The session process never takes this path, so God of War
and Ghost of Tsushima are unchanged. `MADEIRA_CHILD_DESKTOP=0` turns it off.
Host check: `python3 tests/host/check-child-desktop.py` (compiles
get_desktop_window and the helper against a model of the server's per-process
classes; PASS with ASan/UBSan).

Whether this alone clears ERR_GFX_D3D_NOD3D12 is not known: the first DXGI
pass also met a NULL desktop window and did not abort.

### 7.6 Other suspects, not changed here

* **DXGI output identity.** With "Report an NVIDIA GPU" off, DXMT's 64-bit
  DXGI_OUTPUT_DESC::Monitor is its private sentinel (1), not user32's HMONITOR,
  and the output lists only 640x480 / 800x600 / the current mode. That is what
  Ghost of Tsushima's "No installed graphics card ... monitor is connected"
  came from (HANDOFF, build 289). GTA's crash report says "Display : 1920 x
  1080"; the virtual monitor is 1280x720. Test: `env.DXMT_WSI_MONITOR_IDENTITY
  = 1` and `env.DXMT_WSI_MODE_TABLE = 1` in GTA's game file (no build needed).
* **D3DKMT lists no adapter** (`[vkmt] ... 0 adapters (registered GPU is not in
  the list)`, sysparams_ios.c, the virtual-monitor regime): a game or
  Streamline that maps DXGI's adapter LUID to a D3DKMT adapter (driver
  version, WDDM caps) finds none.
* **IDXGIFactory7** and `EnumAdapterByLuid` are not implemented in DXMT (the
  latter would log `DXGIFactory::EnumAdapterByLuid: not implemented`; that line
  does not appear, so it was not called).
* OutputDebugString text after the first four per process is not logged: the
  PE ntdll's `[exc] ml811/ml812` probe allows 4 hits per exception code, and
  madeira-d3d12's own four messages used them up (4646-4669). On ARM64EC,
  RtlRaiseException dispatches in PE code, so the unix side never sees it.

### 7.7 Next device log

On the build with this change, start GTA V Enhanced (either way) with this
line in its game file and send the whole log:

```
env.MADEIRA_GUEST_LOG = all
```

Look for:

* `[child-desktop] madeira-bcd pid=... : no desktop window (status ..., thread
  desktop ...); registered the desktop/message classes for this process; retry 0
  -> top_window=0x...` once, and no `top_window stays 0` after it. If it says
  `thread had no desktop, winstation_init gave it ...`, the child had no
  desktop at all (worth knowing).
* `[guest-log] file .../CrashLogs/crashcontext.log` followed by the whole
  report (adapter, driver, error text) if the game still stops. The mirror
  takes every line of *.log files, 400 lines (`MADEIRA_GUEST_LOG_LIMIT`
  raises it).
* Whether `D3D12CreateDevice(adapter=0x...` now appears after the Streamline
  loads, and whether a game window is created.

If it still ends in 0x80000003 with RSI=0x17b133bd, run once more with

```
env.MADEIRA_GUEST_LOG = all
env.DXMT_WSI_MONITOR_IDENTITY = 1
env.DXMT_WSI_MODE_TABLE = 1
```

(`[monitor-identity] ml1190 using user32 primary=...` confirms the first).

## 8. Build 321: NoExec at GTA5_Enhanced.exe+0x509a144 after the intro video

> **Türkçe özet:** Oyun artık giriş videosunu geçiyor, sonra çocuk süreçte
> (GTA5_Enhanced.exe) emülatörün "çalıştırılabilir" bilmediği bir adrese
> (GTA5_Enhanced.exe+0x509a144) atlıyor ve FEX bilerek erişim ihlali
> üretiyor. Bu adres, emülatörün tanıdığı iki kod bölümünün arasında kalıyor;
> kayıtta bu aralığı çalıştırılabilir yapan hiçbir istek görünmüyor. Bunu
> araştırırken Madeira'nın kendi ntdll.dll'inde gerçek bir hata bulundu: bellek
> korumasını "çalıştırılabilir" yapan isteklerin kayda alındığı tanılama yolu
> (`[exec-req]`), çıkışta `InSyscallCallback` bayrağını temizlemeyi unutuyor.
> Bayrak takılı kaldığı sürece o iş parçacığındaki sonraki bellek değişiklikleri
> (VirtualProtect, VirtualAlloc, DLL eşleme) emülatöre HİÇ bildirilmiyor ve
> kayıtta da iz bırakmıyor. Kayıtta kanıtı var (satır 396 → 450-509; aynı
> DLL'ler çocuk süreçte, öncesinde `[exec-req]` olmadan, normal bildiriliyor:
> 1722-1755). Arxan
> gibi korumalar art arda birkaç aralığı çalıştırılabilir yaptığında ilkinden
> sonrakiler kaybolabilir; GTA'nın çöktüğü aralık tam olarak böyle bir aralık
> olabilir. Düzeltme (yalnızca Madeira tarafı; çatlak/DRM ile ilgisi yok):
> ntdll'in havuz kopyasında üç dal talimatı, bayrağı temizleyen bloğa
> yönlendiriliyor. Diğer oyunları etkilememesi için **isteğe bağlı**:
> `env.MADEIRA_EXECREQ_LEAVE = 1`. Ayrıca iki yeni tanılama satırı her zaman
> açık: `[prot-img]` (ana imajdaki büyük koruma değişiklikleri ve bayrağın o
> anki değeri) ve `[guest-rip-sec]` (NoExec adresinin hangi PE bölümünde
> olduğu ve Wine'ın o sayfaya verdiği koruma). Sonraki cihaz kaydı, bu hatanın
> GTA'nın çöküşünün sebebi olup olmadığını kesin olarak gösterecek.

Log: PlayGTAV.exe 2026-10-02 10:51:28, build 321 (PlayGTAV main, tid 0024,
tracker 0x1488dcb78; GTA5_Enhanced child: boot thread 002c, game thread 0034,
own xtajit64 copy, tracker 0x1500a4b78). Line numbers are this log's.
Earlier log for comparison: PlayGTAV 2026-10-01 20:16:49 (same start-up
sequence, stops at ERR_GFX_D3D_NOD3D12 before reaching this code).

### 8.1 What the child dies on

* 1866-1867: the child's tracker learns GTA5_Enhanced.exe's executable sections
  from the PE headers (FEX `InvalidationTracker::HandleImageMap`,
  IMAGE_SCN_MEM_EXECUTE): `0x140001000-0x14247a400` (.text) and
  `0x145123000-0x145b81000` (the protector's code). Image at its preferred base
  0x140000000, size 0x5b81000, so no relocation is involved.
* 3301-3315: the TLS callback (`[tls-life] ... first=000000014241A754`, thread
  002c, through ntdll's x64 syscall stub) makes four ranges RWX:
  `[exec-req] #17` header, `#18` 0x140001000+0x2479400, `#19`
  0x14247B000+0x3EEE00, `#20` 0x14286A000+0x2741428, each followed by FEX's
  `Add SMC interval` (so these four reached the child's tracker). The protector
  sets "full access" before decrypting, which matches the public Arxan
  write-ups. The ranges end at 0x144FAB428; **0x144FAC000-0x145123000 (RVA
  0x4fac000-0x5123000, 1.5 MB) is never named by any request in the log**.
* 18946-19151: the protector patches .text (`[smc-atomic] #2..#5`, `ml1001
  ... store landed`, e.g. 0x140156c83 `48 8d 14 24` -> `90 90 0f 31`), all
  handled by the SMC path.
* 19158-19161: `[iOS-xquery] MISS tracker=0x1500a4b78 addr=0x14509a144`,
  `NoExec instruction in entry block: 14509A144`, then FEX's deliberate load
  from 0, `[guest-state] rip=0x14509a144`, AV EXEC of 0x14509A144, unhandled,
  crash report (19226 on), NtTerminateProcess 0xc0000005.

0x14509a144 is RVA 0x509a144, in that 1.5 MB gap. On Windows the loader only
gives an image page EXECUTE through the section flags, and FEX read the same
flags, so on Windows either the program makes that range executable at run
time, or the jump target is wrong.

### 8.2 Correction: the child's tracker does get protect notifications

`[iOS-xrem] via=protect` exists for tracker 0x1500a4b78 too (2622, 8025-8031),
and the `Add SMC interval` lines after `[exec-req] #17-#20` are the child's.
Notifications are not routed to the parent's emulator (the earlier bug class).
FEX logs only REMOVALS by protection; an insert by protection (HasExec) is
silent, which is why the log cannot show a successful one.

### 8.3 The bug found: `[exec-req]` leaves InSyscallCallback set

The PE ntdll (`app/Madeira/arm64ec-windows/ntdll.dll`, prebuilt from the wine
fork's `dlls/ntdll/signal_arm64ec.c`) wraps NtProtectVirtualMemory:
`enter_syscall_callback()` sets `CHPE_V2_CPU_AREA_INFO::InSyscallCallback`, the
change is made, FEX is notified, `leave_syscall_callback()` clears the flag.
While the flag is set every memory wrapper (NtProtectVirtualMemory,
NtAllocateVirtualMemory(Ex), NtFreeVirtualMemory, NtMapViewOfSection(Ex))
takes its raw path: no FEX notification, no probe line. That is by design for
calls the emulator itself makes inside a notification.

The ml283 `[exec-req]` probe (first 64 EXECUTE requests per ntdll copy) does
its own syscall, log line and notification and then `return st;` without
`leave_syscall_callback()`. Disassembly of the shipped binary (function at VA
0x1800570f4): the probe's exits at 0x1800573bc (cross-process), 0x1800573c8
(no NotifyMemoryProtect) and 0x1800573f8 (after the notification) all branch to
the epilogue 0x180057514; only the non-exec path passes 0x1800574d8
`ldr x8,[x18,#0x1788]; cbz x8; strb wzr,[x8,#1]`.

The flag is cleared again only when FEX compiles or links a block on that
thread (FEXCore Dispatcher.cpp `EmitSignalGuardedRegion` sets and clears it) or
an exception reaches the guest (`ResetToConsistentState`). Already compiled and
linked code -- a loop calling VirtualProtect -- does neither, so every memory
change after the first executable protect is lost to the emulator.

Evidence in this log, an A/B inside one run: the main process does `[exec-req]
#1` on tid 0024 (396, the loader restoring PlayGTAV's .text, before the
emulator is loaded), and the next four NtMapViewOfSection on that thread --
libarm64ecfex.dll itself and its three imports -- print `insc_before=1
entered=0` (450, 460, 474, 509): none of them was registered with the emulator.
The child loads the same four images with no `[exec-req]` before them and
prints `insc_before=0 entered=1` (1722, 1732, 1744, 1755). (The
create_cross_process_work_list map right after pProcessInit shows
`insc_before=1` in both processes, 696 and 1882: that one is process
initialisation, not this bug.)

What it can explain here: if the program makes the 1.5 MB range executable
right after another executable protect on the same thread, from linked code,
the request is executed by Wine but never reaches FEX and never prints
`[exec-req]`. The log cannot show this by construction, so it is a candidate,
not a proof.

Ruled out on the way: the 99 % CPU samples of thread 0034 inside the unix
NtProtectVirtualMemory (11535-11607, stack values GTA5+0x1000, +0x247a400,
+0x4fac000) are FEX's own SMC trap protects of single pages (made inside its
compile region, flag legitimately set) paying for the IAT-sync pointer scan on
every call, not a lost game request.

### 8.4 Could the target itself be wrong?

* Not a pool alias (a JIT-pool address would be 0x14a0xxxxx+), not a lost high
  half (0x1_4509a144 is a full image address), not a relocation (preferred
  base).
* The gap is the size of a .pdata for 36 MB of code; if it is data, executing
  it is a wrong jump, not a missing permission.
* Candidates on our side: a self-modifying store landing wrong. `ml1001 ...
  0x140c0d1e8 (insn=889ffcdf) LEFT THE BYTES UNCHANGED` (19024) is a release
  store of ZERO (`stlr wzr`); onto bytes that were already zero it looks the
  same, so it is not proof of a drop. Every other checked store landed.
* The protector's own reaction (its timing checks, e.g. the inserted `rdtsc`,
  run very slowly across our SMC round trips) is possible but is not something
  this project works around.

### 8.5 Fix and diagnostics (build/ntdll-unix, no FEX or ntdll.dll change)

* `ios_patch_execreq_leave` / `_current` (virtual_ios.c), called next to the
  `[pc2fh]` patch for the session's ntdll, the EC-child ntdll and a
  pseudo-process child's private copy (loader_ios.c). It finds the probe in the
  image (17 instructions, exactly one match, the blocks it branches to
  checked), checks the same words in this process's pool copy, and rewrites:
  `+0x04 b.eq +0x130` -> `b.eq +0xf4` (0x54000780, the identical cross-process
  block of the non-exec path, which falls into the clear), `+0x10 cbz x11,+0x15c`
  -> `cbz x11,+0x120` (0xb400088b), `+0x40 b +0x15c` -> `b +0x120` (0x14000038).
  Idempotent; any mismatch logs and leaves the copy alone. **Opt-in:
  `env.MADEIRA_EXECREQ_LEAVE = 1`** (Settings > All settings, Memory & JIT
  pool). Off: one `[execreq-leave] off` line, nothing written. On:
  `[execreq-leave] ntdll ... (pool ...): NtProtectVirtualMemory's [exec-req]
  path now clears InSyscallCallback (rva 0x573b8: 54000780 b400088b 14000038)`
  once per ntdll copy (session, then the child).
* `[prot-img]` (always on, first 48 per session): every protect of 64 KB or
  more on the calling process's own main image, with the section it starts in,
  status and `insc=` (the thread's InSyscallCallback; insc=1 means the PE
  wrapper did not tell the emulator).
* `[guest-rip-sec]` (always on, first 8): at a SEGV in emitted code, the image
  section of the guest RIP (from the pool copy's headers, which a protector
  cannot have wiped yet) and Wine's vprot of that page.
* Host check `tests/host/check-execreq-leave.py`: runs the production patch
  against the REAL ntdll.dll laid out as an image (probe at VA 0x1800573b8),
  with an x18-patched pool copy and a child copy; off/0/empty write nothing;
  =1 patches both copies, idempotent, refuses a differing copy and a missing
  probe; a control-flow walk shows the unpatched function reaches `ret`
  without the clear and the patched one never does. PASS (ASan/UBSan).
* The real fix belongs in the wine fork (`leave_syscall_callback();` before
  `return st;` in the `[exec-req]` block of signal_arm64ec.c) the next time
  ntdll.dll is rebuilt; the pool patch then finds no probe layout and says so.

Risk: off by default, so God of War and Ghost of Tsushima only gain the
`[execreq-leave] off` line, at most 48 `[prot-img]` lines (large protects of
their main exe) and 8 `[guest-rip-sec]` lines on a crash. On, the emulator
receives the notifications upstream Wine always sends after an executable
protect; nothing new is called.

### 8.6 Next device log

GTA V Enhanced game file, in addition to the current lines:

```
env.MADEIRA_EXECREQ_LEAVE = 1
```

Read, in order:

1. `[execreq-leave] ... now clears` twice (session ntdll, then the
   GTA5_Enhanced child). `not found exactly once` means a different ntdll.dll.
2. If it still dies with NoExec: `[guest-rip-sec] rip=0x14509a144 = image
   0x140000000+0x509a144, section #N 'name' ... chars ... vprot=0x..`.
   - The section has X: FEX's image registration missed it (FEX side).
   - No X but vprot has EXEC (0x04 bit, e.g. 0x25/0x27/0x2d): Wine made it
     executable and the emulator was not told; find the `[prot-img]` line that
     covers it (`insc=1` = a path still bypassing the wrapper).
   - No X and no EXEC in vprot: nothing made it executable; the target is
     wrong (8.4), and the next step is the jump that leads there, not memory
     protection.
3. If it no longer dies there: run once more WITHOUT the line; a return of the
   NoExec proves the cause, and the `[prot-img]` line for 0x144fac000.. (or
   nearby) will show `insc=1`.

## 9. Build 327: the leak fix works; the child then dies in the PARENT's ntdll

> **Türkçe özet:** `env.MADEIRA_EXECREQ_LEAVE = 1` işe yaradı: oyunun koruma
> katmanı TLS geri çağrısında artık TÜM bölümleri (.pdata, .tls, .rsrc,
> .reloc, ikinci .text ve 0x14509a144'ü içeren küçük bölüm) çalıştırılabilir
> yapıyor ve emülatör hepsini öğreniyor; 321'deki 0x14509a144 çöküşü yok
> oldu (bölüm 8'deki teşhis doğrulandı). Oyun bu yüzden farklı bir yoldan
> ilerliyor ve kendini değiştiren kod çok daha sık tuzağa düşüyor; her
> sistem çağrısı ve istisna ntdll'in KiUserExceptionDispatcher adresinden
> geçiyor. Bu adres 256 kez hata verince Madeira'nın "bayat işaretçi onarıcısı"
> (stale-heal) işaretçiyi havuz kopyasıyla değiştiriyor. Hata burada: çocuk
> sürecin emülatöründeki işaretçi, çocuğun değil ANA sürecin (PlayGTAV) ntdll
> kopyasına çevrildi. Sonraki sistem çağrısı ana sürecin ntdll'inde koştu ve
> çocuğun emülatörünün tanımadığı bir adrese (0x148467050) atladı → çöküş.
> Bu, düzeltmenin yeni ortaya çıkardığı eski bir hata (her çocuk süreçte
> yeterince istisna olunca olurdu). Düzeltme: her havuz kopyası, onu eşleyen
> sürecin adına çevriliyor (varsayılan açık; ana süreçler için hiçbir şey
> değişmiyor; eski kural `env.MADEIRA_HEAL_OWNER = 0`). `[prot-img]`
> satırlarındaki `insc=1` anlamsızdı (bayrak bu noktada her zaman 1) ve
> kaldırıldı. Test: `env.MADEIRA_EXECREQ_LEAVE = 1` satırı kalsın, başka satır
> gerekmiyor.

Logs: PlayGTAV.exe 2026-10-02 11:49:21 and 11:50:19, build 327, both with
`env.MADEIRA_EXECREQ_LEAVE = 1` (plus MADEIRA_DXGI_SRC, MADEIRA_GUEST_LOG=all,
MADEIRA_KMT_ADAPTER, MADEIRA_PAD_MODE=hid). Line numbers are 11:50:19's
unless marked (11:49:21 as "1149:").

### 9.1 Section 8 confirmed

`[execreq-leave] ... now clears` for the session copy (353) and the child copy
(1665). The TLS callback's section pass on thread 002c is now complete and
every request reaches the child's emulator (`[exec-req]` #31-#45, 3317-3359,
each followed by `Add SMC interval`): header, .text, .rdata, .data, **.pdata
0x144FAC000**, 0x145081000, 0x145082000, .tls, 0x145099000, **0x14509A000**
(`Add SMC interval: 14509A000 - 14509B000`, the 4 KB section holding the old
target 0x14509a144), .rsrc, .reloc, 0x14511B000, 0x14511C000 and the
protector's .text 0x145123000. In build 321 the requests after .data (#20)
were the ones lost to the leaked flag. The NoExec at 0x14509a144 does not
occur any more.

The section table, from `[prot-img]`: .text rva 0x1000, .rdata 0x247b000,
.data 0x286a000, .pdata 0x4fac000+0xd4400, .tls 0x5083000+0x15e00, .rsrc
0x509b000, .reloc 0x50ca000, #13 .text 0x5123000+0xa5e000; 0x509a144 lies in
one of the small sections between .tls and .rsrc (#7/#8, under the 64 KB
`[prot-img]` threshold).

### 9.2 The new crash

* 20419-20421: `[iOS-xquery] MISS tracker=0x1500a4b78 addr=0x148467050`,
  `NoExec instruction in entry block: 148467050`, on the child's game thread
  0034 (1149: 27496). 0x148467050 = the SESSION's ntdll copy 0x1483e0000 +
  0x87050 (invoke_arm64ec_syscall), `[rip-leak] ... rva 0x87050` (20424);
  rax = 0x19 (NtQueryInformationProcess), R10 = the x64 stub 0x71ffd55337.
* 20464: the emulator's own rethrow goes to `req pc=0x148441508` = the session
  copy's KiUserExceptionDispatcher, and the next dispatch shows the PARENT's
  ResetToConsistentState (`rtcs=0000000148629588`, 20468; all earlier child
  exceptions show the child's `rtcs=000000014FDF1588`). In build 321 the same
  rethrow went to the PE VA 0x71ffd31508 (1051 log line 19215).

So the child's emulator jumps to the parent's ntdll copy for every syscall and
exception: FEX keeps KiUserExceptionDispatcher in a static
(`Exception::KiUserExceptionDispatcher`, set once in ProcessInit to the PE VA),
and something rewrote it.

### 9.3 Root cause: the stale-pointer heal used the wrong process

```
19748 (1149)  [stale-heal] 0x71ffd31508 crossed 256 faults — queued for heal
20305         [stale-heal] 0x71ffd31508 ESCALATED: rewrote 2 data slot(s) outside IATs
20305         [stale-heal] 0x71ffd31508 -> 0x148441508, rewrote 2 slot(s)
```

The heal (`ios_jit_patch_stale_pointer`, virtual_ios.c; scanner thread
"wine-stale-heal" in signal_arm64_ios.c) rewrites every slot in the module
pool copies that holds a PE VA which exec-faulted 256 times, with the pool
address "for the owner of the copy the slot sits in". Only the per-process
ntdll copies have an owner. The child's emulator (libarm64ecfex.dll at
0x71fcdb0000, pool 0x14fce0000) is a copy with owner NULL, so its slot was
translated like the session's: to the session's ntdll copy. The two slots are
the parent's and the child's FEX statics; the parent's is right, the child's
is the crash.

Why only now: with the leak fixed, the protector's code sections are RWX for
the emulator, so its self-modification traps far more often (`Unhandled JIT
SIGBUS ... 0x39000028`, the ml1065 byte-store retry: 274 lines here, 0 in
build 321). Every trap and every x64 syscall enters KiUserExceptionDispatcher
at its PE VA, one exec-fault redirect each, until the 256th queues the heal.
The bug is older than the fix; any x64 child that exec-faults on an ntdll EC
address 256 times hits it.

### 9.4 Why `[prot-img]` said insc=1 everywhere

The probe sits in the unix NtProtectVirtualMemory. The PE wrapper calls
`enter_syscall_callback()` before the syscall on the notified path too, so the
flag is 1 inside the syscall in every case (main process included: #1-#10 on
tid 0024 all said insc=1). It cannot tell a notified call from a leaked one;
it was a design mistake in section 8 and is removed. What tells them apart is
the PE side's `[exec-req]` line and FEX's `Add SMC interval` after it.

### 9.5 Fix (build/ntdll-unix)

* `struct ios_jit_mapping` gets `map_peb`: the PEB of the process whose thread
  registered the copy (`ios_jit_current_peb()` in ios_jit_add_mapping; the
  child ntdll copy records its owner).
* `ios_jit_patch_stale_pointer` translates each copy for `owner_peb`, else
  `map_peb`. A copy whose process is unknown is left alone when the target
  image has per-process copies (the owner-aware Mach exec-fault redirect keeps
  serving it, one fault per call), with a `[stale-heal] ... left to the
  owner-aware fault redirect` line. Every rewrite in the data pass is named:
  `[stale-heal]   N slot(s) in the copy of <pe> (<module>) -> <target> for
  peb=... (owner=... mapper=...)` (first 32).
  A main process owns no copy, so its translation is the NULL-owner one, as
  before: God of War / Ghost of Tsushima main processes heal exactly as they
  did. **Default on**; `env.MADEIRA_HEAL_OWNER = 0` restores the old rule.
* `[prot-img]`: insc removed (9.4).
* `[guest-rip-sec]` and `ios_image_section_describe` also name a POOL address:
  `POOL copy <jit> (owner=... mapper=...) of <pe>, rva ..., section ...`, so a
  crash like this one says which process's copy the RIP is in.
* Host checks: new `tests/host/check-stale-heal-owner.py` (production heal
  against a model with the session and child ntdll copies, both emulators and
  an unknown-mapper copy; default and `=0`; PASS with ASan/UBSan);
  `check-execreq-leave.py` extended (pool address naming, no insc). Both PASS;
  check-child-ntdll-alias still PASSes.

### 9.6 Found on the way, not changed

* The IAT sync in NtProtectVirtualMemory copies into the FIRST mapping whose
  PE range contains the region. For ntdll that is the session's copy, also when
  a child protects ntdll (its RUNE64 hooks ntdll stubs: `[exec-req]` #11-#30 on
  002c at 0x71ffd60520, 0x71ffd55aa0, 0x71ffd557a0): the child's change lands
  in the PARENT's copy. Owner-aware selection there is the next candidate if
  the parent misbehaves after a child hooks ntdll.
* `[ec-getctx] ml715 ... native_pc=0 -> returned rip=0 rsp=0 flags=00100000`
  right before both crashes: the protector's GetThreadContext(self) gets an
  empty context (no CONTEXT_DEBUG_REGISTERS echoed). Harmless so far; watch it
  if the next run stops in the protector.
* The byte-store SMC retry loop (`Unhandled JIT SIGBUS ... 0x39000028`, 6-8
  retries per store) is slow but lands.

### 9.7 Next device log

Same game file as build 327 (keep `env.MADEIRA_EXECREQ_LEAVE = 1`; no new
line needed). Look for:

1. `[stale-heal] 0x71ffd31508 ... rewrote N slot(s) (each copy translated for
   the process that maps it)` and the per-copy lines: the child's emulator copy
   (0x71fcdb0000) must go to the CHILD's ntdll copy (0x14fba8000 + 0x61508 =
   0x14fc09508), the parent's to 0x148441508.
2. No `NoExec ... 148467050`. If a NoExec appears, its `[guest-rip-sec]` line
   now names the copy and owner.
3. If it still dies: the first `[exc-disp] raise tid=0034` / `[int3-guest]`
   after the heal, and the end of the crash report.
