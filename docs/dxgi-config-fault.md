# GTA V Enhanced: dxgi-src.dll faults in dxmt::Config after a reload

> **Türkçe özet:** `env.MADEIRA_DXGI_SRC = 1` ile her GTA V Enhanced
> oturumunda oyunun 0034 iş parçacığı dxgi.dll+0x2c058'de (NULL okuma) hata
> veriyordu. Sebep DXMT değil, bizim JIT havuzu (pool) kopyası katmanımız:
> GTA5_Enhanced (çocuk süreç) dxgi.dll'i yüklüyor, bırakıyor (FreeLibrary) ve
> AYNI adrese yeniden yüklüyor. `mprotect_exec`'in "bu imaj zaten
> kopyalanmış" denetimi (ml352: yalnız MZ başlığı ve SizeOfImage) eski,
> boşaltılmış modülün havuz kopyasını aynen kullanıyordu. ARM64EC kodu
> global değişkenlerine havuz kopyasından eriştiği için yeni modül eski
> modülün .data/.bss'iyle çalıştı: `Config::getInstance()`'ın statik
> nesnesi DLL_PROCESS_DETACH'ta yıkılmıştı (kova dizisi NULL), ama "inşa
> edildi" bayrağı (guard) duruyordu -> `unordered_map::find` NULL okudu.
> Windows'ta yeniden yüklenen DLL her zaman temiz .data/.bss ile başlar.
> **Düzeltme (ntdll katmanı, her DLL için):** bir imaj görünümü
> boşaltılınca (delete_view) havuz kopyası "boşaltıldı" diye işaretleniyor;
> aynı imaj aynı adrese aynı süreçte yeniden yüklenirse kopyası AYNI havuz
> adresinde baştan kuruluyor (taze .data/.bss, relocation ve x18 yamaları
> yeniden); başka bir durumda yeni kopya alınıyor. Yeniden yüklenmeyen
> modüller için hiçbir şey değişmiyor (God of War / Ghost of Tsushima
> davranışı aynı). Anahtar: `env.MADEIRA_IMAGE_RELOAD` (1 varsayılan, 2 her
> zaman yeni kopya, 0 eski davranış). Bu hatanın GPU uyarısının
> (ERR_SYS_SYSREQ_GPU) sebebi olup olmadığı cihaz testinde görülecek.

Logs: gta1321.log (PlayGTAV.exe 2026-10-02 13:21:28, build 330), and the same
fault in gta1051, gta1149, gta1150, gta1238. dxgi-src.dll rebuilt locally with
the Linux llvm-mingw (1748992 bytes, the size CI ships) for symbols.

## 1. The fault

```
[exc-disp] raise tid=0034 code=c0000005 ... addr=0x71f801c058 pc=154bc4058 p0=0 p1=0
[mach_exc] pc PE: dxgi.dll+0x2c058   lr PE: dxgi.dll+0x2c01c
[guest-rip-sec] rip=0x154b9e020 in image 0x71f7ff0000: POOL copy 0x154b98000
                (owner=0x0 mapper=0x1099dc000) ..., rva 0x6020
x19=0x1 x20=0x13 x2=0x13  (host registers at the fault)
```

GTA's own SEH handler (GTA5_Enhanced.exe+0x2479e30) catches it, the game goes
on, and later shows ERR_SYS_SYSREQ_GPU.

Symbols (local build, `llvm-nm -n`):

| address | symbol |
| --- | --- |
| rva 0x6020 | `dxmt::MTLDXGIFactory::EnumAdapterByGpuPreference` (one symbol there, no identical-code folding) |
| rva 0x2bfcc | libc++ `unordered_map<std::string,std::string>::find` (fault at +0x8c) |
| rva 0x1e5e8 | `dxmt::Config::getInstance()` |
| rva 0xfc568 | guard variable of `getInstance()::config` (.data) |
| rva 0xfc570 | `getInstance()::config` = the `OptionMap` (.data) |
| rva 0xfdd10 | `__mingwthr_cs` (.data, mingw CRT) |

`find` (rva 0x2bfcc):

```
ldr  x27, [x0, #0x8]      ; bucket_count -- nonzero, go on
ldr  x8,  [x0, #0x18]     ; size         -- nonzero, go on
bl   __hash_memory         ; hash of the key, x20 = length 0x13 = strlen("dxgi.customDeviceId")
sub  x19, x27, #1         ; x19 = 1 -> bucket_count = 2 (power of two)
and  x26, x22, x19        ; bucket index 0
ldr  x8,  [x25]           ; bucket array -> NULL
ldr  x8,  [x8, x26, lsl #3]   <- rva 0x2c058, AV READ of 0
```

`getInstance()` (rva 0x1e5e8) is the usual Itanium function-local static:
`ldarb` of the guard at 0xfc568, `__cxa_guard_acquire`, `SingletonConfig()`,
`atexit(dtor)`, `__cxa_guard_release`. Its registered destructor (rva 0x1e854)
frees the nodes and does `str xzr, [x8, #0x570]`: the bucket array pointer
becomes NULL; bucket_count and size stay as they were; **the guard is never
reset** (nothing ever resets a function-local static's guard -- on Windows the
next load of the DLL simply has fresh .data).

So the map is a *destroyed* map: bucket_count 2, size nonzero, buckets NULL.
That is exactly what a second load of the DLL sees if it inherits the first
load's .data.

## 2. The load sequence (identical in all five logs)

gta1321.log (tids 0054 and 0034 both belong to the GTA5_Enhanced child, peb
0x1099dc000: `[ldr-image] ml710 MAP #63 base=00000071F7FF0000 peb=00000001099DC000`
on 0054):

| line | event |
| --- | --- |
| 5090 | `[jit-pool] image 0x71f7ff0000+0x136000 (dxgi.dll) -> pool 0x154b98000` -- load 1, fresh copy |
| 5096 | `D 54 Load module DXGI.DLL ... 71F7FF0000` |
| 5162/5165 | `[dxgi-src] ... first factory request`, `Found config env: dxgi.customDeviceId=2544` -- Config constructed |
| 5176 | `RtlDeleteCriticalSection crit=0000000154C95D10` = pool + 0xfdd10 = `__mingwthr_cs`: DLL_PROCESS_DETACH of dxgi (static destructors run) |
| 5180 | `E 54 [iOS-xrem] via=section ... 0x71f7ff0000-0x71f8126000` -- image unmapped |
| 6129 | `[file-trace] #564 open ... DXGI.DLL` -- load 2 |
| 6132 | `D 34 Load module DXGI.DLL ... 71F7FF0000` -- **same base, and no `[jit-pool] image` line**: the early-out took the old copy |
| 6150-6191 | the fault; `[guest-rip-sec]` names POOL copy 0x154b98000 = load 1's copy; no `[dxgi-src] first factory request` this time (its once-flag is stale too) |
| 6205-6208 | GTA unloads dxgi again: `crit=0x154C95D10` deleted a second time, then `[iOS-xrem]` |
| 7121-7153 | load 3 lands at 0x71f7ef0000 (another DLL took 0x71f8030000 inside the old range: `STALE containment rev=ml352` + purge-on-add) -> fresh copy 0x15549c000 -> works (8532: `first factory request`, `Found config env`) |

gta1051: load 1 at 0x71f8400000 (line 4678), load 2 same base (5406, no
`[jit-pool]`), fault 5466, load 3 at 0x71f8300000 fresh. gta1149/1150/1238:
the gta1321 pattern line for line.

### Why the old copy was adopted

`mprotect_exec` (build/ntdll-unix/virtual_ios.c) copies the WHOLE image into
the JIT pool -- code and data -- because ARM64EC (and x64) code reaches its
globals PC-relative (ADRP / RIP-relative), so the pool copy's .data/.bss is the
module's live data. Before copying it checks whether the range is already in
`ios_jit_mappings`. Since ml352 it validates an entry by reading the MZ header
and SizeOfImage at its PE base; an entry whose module was unloaded and replaced
by the same file at the same address passes that check, and the early-out
returns without copying. Nothing tombstones the entry at unload by default
(`ios_jit_retire_image`, upstream's fix for a DIFFERENT image of the same size
at the same base, is opt-in, `MADEIRA_JIT_IMAGE_RETIRE=1`, set only by Dock
launches; ios_jit_add_mapping's purge-on-add never runs because the early-out
precedes it).

### What it is not

- **[data-align]**: no `[data-align]` line for dxgi.dll (its .data starts at
  rva 0xfc000, already 16 KB aligned); the data is not shifted.
- **Identical-code folding / a bad x64 `this`**: rva 0x6020 carries only
  EnumAdapterByGpuPreference; the faulting map is reached through the
  `getInstance()` static, not through `this`; the key length (0x13) and bucket
  count prove the lookup is the `dxgi.customDeviceId` read of `DxgiOptions`.
- **Static initialisation before the CRT / TLS**: whatever the CRT does at
  the second attach, nothing resets a function-local static's guard; it only
  starts at zero in a fresh .bss.
- **Cross-process sharing**: both loads are in the same pseudo-process.
- **A DXMT bug**: on Windows the second load has fresh .data/.bss and the
  same code is correct. Upstream's dxgi.dll has the same singleton; it is not
  patched.

## 3. Fix (build/ntdll-unix/virtual_ios.c)

1. `struct ios_jit_mapping` gets `unmapped`. `delete_view` of a SEC_IMAGE view
   calls `ios_jit_note_image_unmapped`, which marks every pool copy made from
   that range (after the opt-in retire, before `unmap_area`, under
   `ios_pool_lock`). Nothing is tombstoned, so translations of laggard pointers
   into the unloaded module keep their old target exactly as before. New slots
   (`ios_jit_add_mapping`, child ntdll copies) start unmarked.
2. In `mprotect_exec`'s already-copied loop, an entry that passes ml352 but is
   marked unmapped is decided by `ios_jit_reload_choice`:
   - **rebuild in place** (default) when the copy has no owner (not a
     per-process copy), was mapped by the current pseudo-process, and the new
     view's PE headers (e_lfanew to the end of the section table, read
     fault-safely) are byte-identical to the copy's: the normal copy path runs
     with the old pool offset instead of a new allocation -- the image is
     memcpy'd again from the new view (fresh .data/.bss), DIR64 relocations
     and x18 trampolines are redone (byte-identical for identical code, at the
     same fixed image-relative tramp offset), the data sections are made RW
     again, and `ios_jit_add_mapping` re-registers the same jit base (its
     overlap purge drops the old entry; FEX's `BTCpu64IosAddAliasMapping` sees
     an identical registration and keeps it). No pool space is used, the
     emulator's translations stay valid, the range stays in this process's
     ledger. Guard (`ios_pool_ledger_holds`): the rebuild runs only when one
     pool-ledger record of the current process holds the old offset plus the
     new image and trampoline size; otherwise `[image-reload] in-place
     rebuild dropped ... -- new pool copy`.
   - **new copy** otherwise (another process, a per-process copy, different
     headers, or mode 2): the entry is skipped like a ml352-stale one; the copy
     path allocates a new range and the purge-on-add retires the old entry.
3. `env.MADEIRA_IMAGE_RELOAD`: `1` (default) as above, `2` always a new copy
   (fallback if the in-place rebuild misbehaves; costs pool space per reload),
   `0` old behaviour (nothing marked).

Logs: `[image-reload] madeira-bcd mode=N (...)` once; `[image-reload] unmapped
image <base>+<size>: N pool cop(y|ies) marked` (32 max); `[image-reload]
<dll> <base>+<size> loaded again at the base of its unloaded pool copy ... ->
rebuilding that copy in place | new pool copy` and `[image-reload] <dll>
rebuilt in place: pool ...` (32 max). The rebuilt image's ordinary
`[jit-pool] image ...` / `[x18-patch]` lines follow. Expect `[poison-step]
pre-memcpy: N non-exec pages` on an in-place rebuild: the copy's data pages
were made RW at its first copy (diagnostic only).

Who is affected: only a module unloaded and loaded again at the same address.
Every first load, every load at a new address, every second section of a
loaded image, and every runtime VirtualProtect on a loaded image take the
same path as before. God of War and Ghost of Tsushima change only if they do
reload a DLL at the same base -- and then they get what Windows gives them.
Dock launches (`MADEIRA_JIT_IMAGE_RETIRE=1`) keep retiring at unload; the
marked entries are gone before a reload can see them.

## 4. Checks

- `tests/host/check-image-reload.py` (new): compiles the production helpers
  (`ios_image_reload_mode`, `ios_jit_note_image_unmapped`,
  `ios_jit_reload_choice`, `ios_jit_same_headers`, the real
  `struct ios_jit_mapping`) with ASan/UBSan against a model of the GTA case
  (dxgi copy mapped by the child, a per-process copy of the same image, the
  next image up): data views and neighbours unmarked, same image/base/process
  -> in place, other process / owned copy / different headers / unreadable
  view -> new copy, live entry -> old early-out; modes 0/1/2 and bad values;
  and checks the call sites (delete_view order, slot clearing, the decision
  sits after ml352 and before the early-out, the in-place offset skips the
  allocation and the second data-align shift). PASS.
- check-image-retire, check-stale-heal-owner, check-child-ntdll-alias,
  check-execreq-leave, check-lazy-windows, check-small-va-band,
  check-unixlib-binder: PASS. (check-swap-coverage fails identically on the
  unmodified file; check-wma-decoder needs a configured Wine tree.)
- Differential `clang -fsyntax-only` of virtual_ios.c (old vs new, stub Mach
  headers): identical error set, no warning in the changed lines.
- Config catalog regenerated (one new row, `env.MADEIRA_IMAGE_RELOAD`).
- dxgi-src.dll is not changed.

## 5. Device test

GTA V Enhanced with the usual game file (`env.MADEIRA_DXGI_SRC = 1`), nothing
else new. Expect in the log:

- `[image-reload] unmapped image 0x71f7ff0000+0x136000: 1 pool copy marked`
- `[image-reload] dxgi.dll 0x71f7ff0000+0x136000 loaded again at the base of
  its unloaded pool copy 0x154b98000 ... headers identical) -> rebuilding that
  copy in place` and `[image-reload] dxgi.dll rebuilt in place: pool ...`
  (addresses vary per run);
- a second `[dxgi-src] ... first factory request` and `Found config env`
  around the second load;
- no `c0000005` at `dxgi.dll+0x2c058`.

Then: does ERR_SYS_SYSREQ_GPU still appear? If it does, the fault was not its
cause; continue with the GPU-check values (D3D12 feature level, Agility SDK,
adapter description) -- see docs/gta5-d3d12-caps.md. If anything new breaks
around a DLL reload, `env.MADEIRA_IMAGE_RELOAD = 2` (new copy) and then `= 0`
(old behaviour) narrow it down.
