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
