# Hardware description keys (HKLM\HARDWARE\DESCRIPTION\System)

> **Türkçe özet:** Masaüstü Wine'da (ve Proton'da) `wineboot` her açılışta
> geçici (volatile) donanım anahtarlarını yazar: `HARDWARE\DESCRIPTION\System`
> altında `CentralProcessor\N` (işlemci adı, üretici, ~MHz, FeatureSet),
> `FloatingPointProcessor\N` ve `BIOS` (SMBIOS'tan üretici/model/sürüm).
> iOS'ta wineboot hiç çalışmadığı için bu anahtarlar oturumlarımızda **hiç
> yoktu**: GTA V Enhanced'ın donanım bilgisi iş parçacığı `CentralProcessor\0`
> ve `BIOS` anahtarlarını açamıyordu (build 332, 15:13:38 logu, trace+reg),
> WMI'nin Win32_Processor.Caption değeri boştu. Artık oturumun ilk süreci,
> işlemci sayısı belli olur olmaz bu anahtarları wineboot'un yazdığı adlarla
> ve geçici olarak yazar. İşlemci değerleri misafirin (x86-64 oyun) FEX
> üzerinden gördüğü CPU'yu anlatır: `Intel64 Family 6 Model 166 Stepping 1`,
> `GenuineIntel`, `Unknown ARM CPU`, ~MHz 1536 (FEX'in ölçeklenmiş TSC'si);
> GetSystemInfo'nun bildirdiği her işlemci için bir anahtar. BIOS değerleri
> oyunun GetSystemFirmwareTable ile gördüğü SMBIOS tablosundan gelir (iPhone'da
> büyük olasılıkla `Apple Inc.` / `iPhoneXX,Y`), boş olan yerlerde Wine'ın
> kendi varsayılanları (`The Wine project` / `Wine` / `11.4`). Varsayılan
> olarak açık; `env.MADEIRA_HW_REGISTRY = 0` kapatır, `= 2` ayrıca wineboot'un
> Session Manager\Environment'taki beş işlemci değerini de günceller
> (önek şablonunda 16 işlemci ve "Model 44" yazıyor). Logda tek satır:
> `[hw-registry] ...`. God of War / Ghost of Tsushima için tek değişiklik bu
> anahtarların artık var olması.

## What was missing

Desktop Wine runs `wineboot` at every prefix start; its
`create_hardware_registry_keys` (`programs/wineboot/wineboot.c`) writes the
**volatile** tree `HKLM\Hardware\Description\System` from
`NtQuerySystemInformation(SystemCpuInformation)` and the SMBIOS table
(`GetSystemFirmwareTable('RSMB')`). On iOS wineboot never runs (no
fork/exec, `build/ntdll-unix/env_ios.c`), the prefix template's `system.reg`
has no `HARDWARE` subtree at all (volatile keys are never saved), and nothing
in `build/` or `app/` created one. Evidence: GTA V Enhanced, build 332, log
`PlayGTAV.exe 2026-10-02 15:13:38` with `WINEDEBUG=...,trace+reg`, thread
0054 (its hardware-info worker):

```
0054:trace:reg:NtOpenKeyEx (0x14,L"HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0\\",20019,...)
0054:trace:reg:NtOpenKeyEx <- 0x0
0054:trace:reg:NtOpenKeyEx (0x14,L"HARDWARE\\DESCRIPTION\\System\\BIOS\\",20019,...)
0054:trace:reg:NtOpenKeyEx <- 0x0
```

Readers of these keys: WMI (`dlls/wbemprox/builtin.c`: Win32_Processor.Caption
is the `Identifier` value; it was NULL), games' system-requirement and
telemetry code, crash reporters, launchers that build a machine ID from
`ProcessorNameString` (a WineHQ forum thread, "ProcesserNameString not
found", [t=25108](https://forum.winehq.org/viewtopic.php?f=8&t=25108), is
such a program failing when the value cannot be read), anti-tamper hardware
checks. Proton users always have the keys (Proton runs wineboot).

## What is written now

`ios_hw_registry_publish` (`build/ntdll-unix/server_ios.c`), called from
`start_main_thread` (`loader_ios.c`) right after `init_cpu_info()` -- the
processor count is known, the SMBIOS table can be built -- and before
`init_startup_info` reads `Session Manager\Environment`. Only the session's
first process runs `start_main_thread`; pseudo-process children use the same
wineserver registry. Every key is created level by level with
`REG_OPTION_VOLATILE` (the helper the HID pad uses: Wine 11's `NtCreateKey`
makes one key and fails over a missing parent), so nothing is saved with the
prefix. The values are built in `build/ntdll-unix/hw_registry_ios.h` (plain C,
host-tested).

| Key (under `HKLM\HARDWARE\DESCRIPTION\System`) | Value | Written | Source |
|---|---|---|---|
| (the key) | `Identifier` | `AT compatible` | wineboot constant for x86/x64 |
| | `SystemBiosDate` | `01/01/70` | wineboot constant |
| `CentralProcessor\N`, N = 0..count-1 | `Identifier` | `Intel64 Family 6 Model 166 Stepping 1` | wineboot's AMD64 format over FEX's family/revision |
| | `VendorIdentifier` | `GenuineIntel` | FEX CPUID leaf 0 |
| | `ProcessorNameString` | `Unknown ARM CPU` | FEX CPUID 0x80000002-4 |
| | `FeatureSet` (DWORD) | `0x2379ffff`, `0xe3f9ffff` with AVX (64-bit main image) | FEX's ProcessorFeatureBits |
| | `~MHz` (DWORD) | `1536` (24 MHz counter) | FEX's guest TSC rate |
| `FloatingPointProcessor\N` | `Identifier` | as CentralProcessor | wineboot |
| `BIOS` | `BaseBoardManufacturer/Product/Version`, `BIOSVendor/Version/ReleaseDate`, `SystemManufacturer/ProductName/Version/SKU/Family` | SMBIOS strings | the guest's `GetSystemFirmwareTable('RSMB')` |
| | `BiosMajorRelease`, `BiosMinorRelease`, `ECFirmwareMajorVersion`, `ECFirmwareMinorVersion` (DWORD) | from the SMBIOS BIOS entry (0xff on Wine's tables) | wineboot's rule (0xff below length 0x18) |

**count** = `peb->NumberOfProcessors`, i.e. what GetSystemInfo reports (the
device's online cores, or `cpu-count` / `MADEIRA_CPU_COUNT`), clamped to 1..64.

**Why the x86-64 view.** The guest is x86-64 code under FEX. Its GetSystemInfo
already says AMD64, family 6, revision 0xA601 (FEX's
`UpdateProcessorInformation` hook in the ARM64EC ntdll), and its CPUID says
GenuineIntel / family 6 model 0xA6 stepping 1 / brand "Unknown ARM CPU". Stock
wineboot builds exactly these values from the same SYSTEM_CPU_INFORMATION and
the SMBIOS processor strings, so the registry now agrees with what the game
measures itself. The numbers are mirrored from FEX's source, and
`tests/host/check-hw-registry.py` reads each one back out of it:
`FAMILY_IDENTIFIER` (CPUID_AMD undefined), the vendor words, the iOS
`FetchHostFeatures` publishing one MIDR (0, which the MIDR table maps to
`ARM_UNKNOWN` = "Unknown ARM CPU" on every core), the `CPUFeatures` baseline
bits plus SSE4.2 (SupportsCRC, always set on iOS ARM64EC) and
XSAVE/AVX/AVX2 when `MADEIRA_FEX_AVX=1` and the main image is 64-bit
(`tools/patch-fex-ios-avx.py` is built into the ARM64EC module only; a 32-bit
main image runs the WOW64 module, which has no AVX). Library launches are
always ARM64EC or WoW64; only developer test programs run as native ARM64
(`cube.exe`), and for those the x86-64 values are not what GetSystemInfo
says.

`~MHz` follows wineboot's meaning (the TSC rate): FEX's SmallTSCScale doubles
`CNTFRQ_EL0` until it reaches 1 GHz and CPUID 0x15 reports that rate; Apple's
counter runs at 24 MHz on iOS and macOS
([ARMSX2 #717](https://github.com/ARMSX2/ARMSX2/pull/717)), so the guest's
TSC and `~MHz` are 1536. If the counter read gives 0, wineboot's fallback
(`NtPowerInformation` MaxMhz) is used.

**BIOS strings.** Read from the SMBIOS table the guest itself gets, with
wineboot's field rules (SKU and family only from length 0x1B, the release
bytes only from 0x18), so the registry and WMI's Win32_BIOS / Win32_BaseBoard
agree. On Apple hosts ntdll builds that table from IOKit's
`IOPlatformExpertDevice` (`manufacturer`, `model`): on the phone that should
be `Apple Inc.` / `iPhoneXX,Y` -- the host's own identity, as stock Wine shows a
Mac's model; nothing is invented. Where the table lacks an entry or a string
(IOKit may hide properties from the sandbox) the value is the one ntdll's
generic table uses: `The Wine project`, `Wine`, the Wine version (`11.4`),
`01/01/2021`. Deviation from wineboot: wineboot writes `""` for a missing
string and nothing for a missing entry.

## Switch and log

`env.MADEIRA_HW_REGISTRY` (madeira.cfg or the game's own file; read once at
session start):

* unset / `1` (default): the keys above.
* `0`: nothing is written (the session is as before this change).
* `2`: the keys, plus wineboot's five values in
  `HKLM\System\CurrentControlSet\Control\Session Manager\Environment`
  (`PROCESSOR_ARCHITECTURE` AMD64, `PROCESSOR_IDENTIFIER`, `PROCESSOR_LEVEL`,
  `PROCESSOR_REVISION`, `NUMBER_OF_PROCESSORS`), rewritten only where they
  differ. These are saved with the prefix and become the processes'
  environment variables. The prefix template still carries the values of the
  machine that built it (`NUMBER_OF_PROCESSORS=16`, `Intel64 Family 6 Model 44
  Stepping 0`, the CPU Rosetta 2 reports, so most likely an Apple Silicon
  Mac), while GetSystemInfo says 6. Opt-in because it changes every game's
  environment; once written they stay (saved) after the switch goes back to
  1 or 0, as they would in a desktop Wine prefix.

The keys are volatile: they vanish when the wineserver exits (at the latest
when the app restarts), so `0` takes full effect from then on.

One line per session:

```
[hw-registry] madeira-bcd: HKLM\HARDWARE\DESCRIPTION\System (volatile): 6/6 CentralProcessor + 6 FloatingPointProcessor "Intel64 Family 6 Model 166 Stepping 1" GenuineIntel "Unknown ARM CPU" ~MHz 1536 FeatureSet 0x2379ffff; BIOS "Apple Inc." "iPhone18,2" (SMBIOS, 0 Wine default(s)); MADEIRA_HW_REGISTRY=0 turns it off
```

(the BIOS strings are whatever the phone's table holds; `no SMBIOS table, 9
Wine default(s)` when ntdll has none), `...; Session Manager\Environment: 3 of
5 processor values rewritten` with `= 2`, or `[hw-registry] madeira-bcd:
MADEIRA_HW_REGISTRY=0, no HARDWARE\DESCRIPTION keys written`.

## Effect on other games

God of War and Ghost of Tsushima only gain the keys. Nothing in this
repository, DXMT, madeira-dock or Wine except wbemprox reads them. FEX's iOS
build (`FEX_IOS_HOST`, both modules) synthesizes its host features and never
opens `CentralProcessor` (note: FEX's non-iOS `FetchHostFeatures` reads the
ARM64 ID registers `CP 4000`... from these keys, which wineboot writes only on
ARM64 hosts; if the iOS path is ever dropped, those values are needed too). At
startup the publish call builds the SMBIOS table and the logical-processor
cache a little earlier than the first game query would have (same inputs,
same result), costs about two hundred in-process registry calls once per
session, and logs one line. `MADEIRA_HW_REGISTRY=0` restores the old state.

## Not changed (open)

* WMI Win32_Processor.Name / Manufacturer come from the SMBIOS processor
  entry, which ntdll builds from the ARM host (`cpu_vendor` "ARM", empty
  `cpu_name` -> "Unknown CPU"), not from FEX's view; MaxClockSpeed comes from
  NtPowerInformation (1000 MHz, Wine's canned value when `hw.cpufrequency` is
  absent). Making those agree with CPUID needs a patch to
  `dlls/ntdll/unix/system.c`.
* `SystemBiosVersion` / `VideoBiosVersion`, `Configuration Data`, `Component
  Information`, `MultifunctionAdapter`: real Windows has them, stock wineboot
  writes none; not added.
* The brand string "Unknown ARM CPU" is FEX's (one synthetic MIDR on iOS); a
  real name would have to come from FEX itself so CPUID and registry stay equal.

## Test

`tests/host/check-hw-registry.py` (`WINE_SRC`, `FEX_SRC` point at checkouts of
the pinned submodules; default `./wine`, `./FEX`): wiring; the values;
every mirrored FEX number read back from the FEX sources; wineboot's value
names, constants and formats; wineboot's own SMBIOS parser and ntdll's own
SMBIOS generator extracted, compiled and compared with ours on Wine's generic,
Apple, SMBIOS 2.3 and incomplete tables; a parser fuzz run (every truncation,
100000 mutations) under ASan/UBSan; the publish code compiled with `-Werror`
against Wine's headers and run on a fake registry with Wine 11's parent rule
(volatility, values, rerun, `0`, `2`, AVX, no SMBIOS, zero counter). Passes
with gcc 13 and clang 18. The iOS build itself (server_ios.c, loader_ios.c)
is checked by CI.

## Device test

Any game, normal settings. Expect the `[hw-registry]` line above early in the
log, after the first process's `[drives] published ...` line and before its
DLLs load. With `env.WINEDEBUG = err+all,err-virtual,trace+reg` GTA V's
thread now gets a handle for `HARDWARE\DESCRIPTION\System\CentralProcessor\0\`
and `...\BIOS\` and queries their values. `env.MADEIRA_HW_REGISTRY = 0` brings
back the old behaviour; `= 2` for the Environment values (look for `processor
values rewritten`).
