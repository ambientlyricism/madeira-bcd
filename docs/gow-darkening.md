# God of War darkens below 1080p: evidence, candidates, switches, device test

> **Türkçe özet:** Kök neden henüz kanıtlanamadı; ama loglar sorunu
> daralttı. (1) Hareketsiz ana menü sahnesinde oyunun her kare geri okuduğu
> pozlama değeri (16 bayt, `[rb-buf]`: x = log parlaklık, z = toplam) iç
> çözünürlüğe göre değişiyor: 1080p'de x=4.37/z=4460, 720p'de (sınır
> kontrolü açık) 2.26/3120, 754x424'te (FSR) -0.84/1095. Aynı sahne aynı
> değeri vermeli; yani 1080p altında oyunun parlaklık ölçümü yanlış girdi
> okuyor (çoğunlukla "kara" girdi), arada bir doğru değer sızınca (sıçrama)
> pozlama düşüyor = kararma. (2) Oyun, parlaklık hedeflerini yaratmadan hemen
> önce kenar rengi (32,32,32,32) olan bir örnekleyici (sampler) yaratıyor;
> Metal bu rengi bilmiyor, DXMT onu 1.0 (beyaz) yapıyor -- D3D 32 döndürür.
> (3) Bizim DXMT sürümümüzde D3D11'in kaynak çakışma kuralları (aynı doku hem
> okunur hem yazılırsa okumayı sıfırlamak; OMSetRenderTargets'ta UAV'leri
> çözmek) yok; bunlar 64-bit PE d3d11.dll'de, değiştiremiyoruz. Bu dal hiçbir
> varsayılanı değiştirmiyor; tek bir cihaz oturumunda birkaç hipotezi ayırt
> etmek için açılıp kapatılan anahtarlar ve bir GPU izi ekliyor. **Test:**
> bölüm 6 -- her denemede önce 30 sn ana menüde bekleyin (menüdeki x/z
> değeri 1080p'dekiyle aynı çıkarsa o anahtar çözümdür), sonra gökyüzü
> görünen bir yere çıkın.

Branch `worktree-agent-a5c1a7a822d9c74ce`, 2026-10-01. Logs are in the
session's upload directory (`/root/.claude/uploads/4b0cf699-.../`); line
numbers refer to those files.

| Log | Build | Display / internal | Bounds (MADEIRA_LD_BOUNDS) | Notes |
|---|---|---|---|---|
| `484d247b-GoW.exe-2026-10-01_19-33-23.txt` | 294 | 1920x1080 / 1920x1080 | off | reference: never darkens |
| `1bf663aa-GoW.exe-2026-10-01_19-16-44.txt` | 294 | 1280x720 / 754x424 | off | FSR 2 on by mistake (owner) |
| `b09c526e-GoW.exe-2026-10-01_15-52-42.txt` | 282 | 1280x720 / 1280x720 | on | darkening "~20 % milder" |
| `44c62cbc-GoW.exe-2026-10-01_15-06-44.txt` | 279 | 1920x1080, FSR on at the end | n/a | darkens once FSR is on |
| `ef079d1b-...14-51-20.txt`, `5cd9b4b3-...11-56-52.txt`, ... | 271-279 | 1568x720 / 1280x720 etc. | n/a | all darken outdoors |
| `ed0c35c2-GoW.exe-2026-10-01_17-08-27.zip` (M1 iPad) | 291 | 640x480 / 320x200 | on | black scene |

## 1. What the logs show

### 1.1 The game's exposure state, read back every frame

The 16-byte buffer readback that the readback census logs (`[rb-buf]
madeira-bcd value 16 bytes -> x e z w`) is the game's exposure state: x a log
luminance, e the applied exposure factor, z a luminance sum. The main menu
(phase with e = 0.0175) shows a static 3D scene, so its x/z should not depend
on the render resolution. They do:

| run | internal res | menu x / z | lines |
|---|---|---|---|
| 1080p (294, bounds off) | 1920x1080 | **4.37 / 4460** (4.43/4660 settling) | 484d247b: 13647, 16019-20820 |
| 720p (282, bounds on) | 1280x720 | **2.26 / 3120** | b09c526e: 15275-23866 |
| 720p + FSR balanced (294, bounds off) | 754x424 | **-0.84 / 1095**, one frame 4.42 / 4173 | 1bf663aa: 13963-24406, spike 18617 |

In the house after loading (e = 0.053 in both, the area's fixed exposure):
1080p x = 4.39, z = 3530 (484d247b: 26287-27881) vs 754x424 x = -0.94, z = 1037
(1bf663aa: 30012-36914). Outdoors at 720p (282) x sits near -0.15, z ~1500,
and every few tens of seconds one or two readbacks jump to the "1080p-like"
range -- 5.38/4374 (b09c526e: 31627), 6.09/5216 and 5.98/5117 (36606,
36680), 5.65/4816 and 5.76/4702 (38093, 38167) -- after which e falls from
~0.07 to 0.027-0.032 (37264-37818) and climbs back over ~10 s: that is the
visible darkening. The M1 iPad (320x200) shows the mirror image: mostly
x = 5.9-7.3 with e crushed to 0.0156 (black), and occasional -0.95/1014
(ed0c35c2: 107270, 228099, 379039).

Reading: below 1080p the luminance measurement mostly sees a far darker scene
than the same frame at 1080p (x pinned near -0.9, a "black input" value that
recurs on two different devices: iPhone 754x424 house -0.938/1037, iPad
-0.947/1014 and -0.98/1008), and the true value only leaks through on some
frames. The auto exposure, adapting fast towards darker and slowly towards
brighter, turns those leaks into the slow dark-and-recover waves. Whatever the
cause is, it makes the *input* of the luminance chain resolution-dependent.

### 1.2 A border-color sampler created together with the luminance targets

Every log has `warn: CreateSamplerState: Unsupported border color (32, 32,
32, 32)` right before the first float target set (R32F 1920x1080, RGBA32F
240x135, ...): 484d247b: 8110 -> 8125; b09c526e: 8099; ed0c35c2: 8146.
DXMT (d3d11_state_object.cpp:742-760, the committed PE `d3d11.dll`) maps any
border color Metal cannot express to opaque white, so a sample outside the
texture with that sampler returns 1.0 where D3D11 returns 32.0. Upstream DXMT
(fb45156, 2026-10-01) still has no custom border colors.

The sampler is created a second time (a new descriptor, i.e. a changed
MipLODBias) exactly when the render scale drops below the output: FSR at
1280x720 output (1bf663aa: second set 10534-10537, sampler 10559), FSR at
1080p output (44c62cbc: second set 41088-41091, samplers 41148 and 41402),
the iPad's 320x200 of 640x480 (ed0c35c2: second set 48569-48612, sampler
48772). At native 720p it is not re-created (b09c526e has only 8099).

### 1.3 The second target set

At 1080p the game keeps the float targets it creates at start-up (R32F
1920x1080 usage RT+UAV+SRV, RGBA32F 240x135, R32F 2048x1024, 960x540,
128x64 (8 mips), 60x34, 64x32 (7 mips): 484d247b 8125-9086). Below 1080p it
creates a second set: 1280x720 / 160x90 / 640x360 / 40x23 (b09c526e
10283-10331), 754x424 / 95x53 (1bf663aa 10536-10537), 320x200 / 40x25 /
160x100 / 10x7 (iPad). The 1/8-resolution RGBA32F and the 1/32 R32F grid
are ceil(size/8) and ceil(size/32): 1080/32 = 33.75 -> 34 rows (one partial
row), 720/32 = 22.5 -> 23, 424/32 = 13.25 -> 14, 200/32 = 6.25 -> 7. The 1/8
-> 1/32 step reads 4 rows per tile: one row past the bottom at 1080p, two at
720p, three at 424 and 200. Such out-of-range reads are where the D3D rules
(0 for `ld`, the border color for border-mode `sample`) decide the value.

### 1.4 No DXMT warnings or errors specific to the low resolution

The set of DXMT `err:`/`warn:` messages is the same in the 1080p and the
754x424 log apart from the background-execution errors at the end of a
session (nothing like "uav only rendering is enabled but viewport is empty",
which would drop a pass).

## 2. What was checked in the code

* **ld / ld_uav_typed / store_uav_typed bounds (builds 282, 284).** Reviewed
  `madeira_ld_in_bounds`: mip < mip count, unsigned compare of each
  coordinate against the size at that mip, array slice < array length, the
  read at a clamped address, the result selected to 0; stores branch around
  the write. Correct D3D semantics; compiled and converted on the host (section 5)
  -- the IR is what was intended. They cannot make the picture darker than
  D3D (D3D returns the same 0). Not covered by them: typed-buffer views (DXMT
  emulates the view offset, so an out-of-range index reads neighbouring data;
  upstream fixed it in 3bcaf16, 2026-06-01), texture atomics, resinfo on a mip
  past the last -- now `MADEIRA_BOUNDS_EXTRA`.
* **resinfo / bufinfo / sampleinfo** (`nt/dxbc_converter_base.cpp`): sizes
  from the bound view at the requested mip, mip count from the view; nothing
  resolution-specific. Out-of-range mip -> Metal undefined (D3D: 0) ->
  `MADEIRA_BOUNDS_EXTRA`.
* **GroupMemoryBarrier()** (DXBC `sync_g` without `_t`) is converted to
  *nothing* (`nt/dxbc_converter_base.hpp` InstSync); groupshared accesses are
  volatile loads/stores but Metal does not keep them coherent inside a SIMD
  group without `simdgroup_barrier` -- upstream added a pass for exactly this
  ("some games expect shared memory to be coherent within a warp", a4cfaac,
  2026-04-14, after our pin) -> `MADEIRA_TGSM_SYNC`.
* **sample_l** ignores the sampler's MipLODBias (DXMT emulates the bias in the
  shader, only for implicit-LOD sampling); D3D and Vulkan apply it; upstream
  fixed it in eec0b65 (2026-06-01) -> `MADEIRA_SAMPLE_L_BIAS`. Only matters
  when the game biases its samplers -- FSR and the iPad's render scale (1.2),
  not native 720p.
* **Fast math**: airconv sets contract/reassoc/arcp/afn/nsz on compute and
  pixel shaders and uses `air.fast_*` functions -> `MADEIRA_PRECISE_MATH`
  rules all of it in or out at once (PS_CLAMP and PRECISE_MINMAX were
  refuted on build 277).
* **Clear kernels** (`dxmt_command.metal`) bound-check; render passes without
  attachments take their size from viewport 0; the clear-into-render-pass
  merge only matches whole attachments; encoder reordering only swaps
  encoders without a data dependency (bloom filter, false positives only).
  Nothing resolution-specific found.
* **D3D11 binding hazards are not implemented in our DXMT** (PE side): no
  SRV unbinding when a resource is bound as RTV/UAV (`FIXME: resolve srv
  hazard` in `d3d11_context_impl.cpp` SetUnorderedAccessViews; upstream
  2b688f8/d079b56/d068c86, 2026-04-07) and OMSetRenderTargets keeps
  pixel-shader UAVs bound (upstream 7d59ed1, 2026-04-08). D3D11 and DXVK
  null such an SRV (the shader reads 0) and drop writes to an unbound UAV.
  Not fixable from native code; the GPU trace flags what it can see
  (`HAZARD`, `uav:` lists).
* Our pin is upstream aeb5fa6 (2026-04-01) plus Madeira changes (airconv
  `nt/` and `airconv_context.cpp` byte-identical to aeb5fa6). Other upstream
  airconv fixes after it, not ported: udiv by zero (46b1146), firstbit_shi
  (ffd907f, d1c926c), NaN sample coordinates (f48f4c7, opt-in upstream),
  fma defusion (59bf42f, opt-in), texture queries on a null descriptor
  (64ee6f5).

## 3. Ranked candidates

1. **The luminance chain reads something else than on D3D at the edge or in
   a stale binding** (most consistent with 1.1-1.3: resolution-dependent,
   "black" input, rare correct frames):
   a. border-mode samples outside the texture (D3D 32.0, DXMT 1.0) --
      test: `MADEIRA_BORDER=black` changes 1.0 to 0.0; if the menu x/z move,
      border sampling is in the chain. A real fix needs the PE `d3d11.dll`
      (pass the border color to the shader) -- see 7.
   b. D3D11 hazard nulling / UAV unbinding missing (PE) -- test: the trace's
      `HAZARD` lines and the `uav:` lists of render passes.
   c. typed-buffer / atomic / mip-range out-of-range access --
      `MADEIRA_BOUNDS_EXTRA=1` (correct D3D semantics).
2. **Warp-synchronous groupshared reductions** (luminance / histogram
   reductions are the classic case; upstream needed a fix for "all games I
   know") -- `MADEIRA_TGSM_SYNC=1`. Does not explain the resolution
   dependence by itself.
3. **Stale tile memory** (a render pass that starts from DontCare and stores
   regions it did not draw) -- `MADEIRA_RP_LOAD=1`.
4. **Fast math** -- `MADEIRA_PRECISE_MATH=1`.
5. **sample_l without the sampler bias** (FSR / render scale only, also the
   iPad) -- `MADEIRA_SAMPLE_L_BIAS=1`.
6. **NaN/Inf in the HDR chain** (iPad's `nan` readbacks) -- the value dumps
   count NaN/Inf per target.

## 4. What changed (all OFF by default)

With none of the switches below set, the converted shaders are byte-identical
to build 294's (checked on the host, section 5), the shader-cache salt is unchanged
(existing caches stay valid) and the native hooks only test a flag.
**God of War at 1080p is not affected by default.** The only default-visible
change is up to 8 `[border]` log lines.

`tools/patch-airconv-gow-experiments.py` (CI step "Patch airconv God of War
experiments", after "Patch winemetal GPU timeline for [frame]"):

| switch | what | D3D semantics? | cache salt |
|---|---|---|---|
| `MADEIRA_TGSM_SYNC=1` | upstream a4cfaac simdgroup barrier after groupshared stores feeding loads (kernels), plus `sync_g` -> simdgroup barrier; `[tgsm-sync]` names the first kernels touched | emulates PC GPUs' warp coherency (upstream default) | +1000 |
| `MADEIRA_SAMPLE_L_BIAS=1` | sample_l LOD += sampler MipLODBias (upstream eec0b65) | yes | +2000 |
| `MADEIRA_PRECISE_MATH=1` | no fast-math flags, precise `air.*` functions | stricter than D3D | +4000 |
| `MADEIRA_BOUNDS_EXTRA=1` | typed UAV atomics (2D/2D-array/3D, typed buffers) skipped out of range (result 0); typed-buffer ld/ld_uav_typed read 0 and stores are dropped outside the view (upstream 3bcaf16); resinfo of a mip past the last returns 0 sizes | yes | +8000 |
| `MADEIRA_SHADER_DUMP=cs,ps,...,<sha8>` | DXBC of created shaders to `Documents/shader-dump/<sha1>.<type>.dxbc` (256 MB cap) | -- | none |

`[gow-exp] madeira-bcd converter experiments: TGSM_SYNC=.. SAMPLE_L_BIAS=..
PRECISE_MATH=.. BOUNDS_EXTRA=..` is logged once at the first conversion.

`tools/patch-winemetal-gpu-trace.py` (CI step "Patch winemetal GPU trace and
render-pass experiment", right after it):

* `MADEIRA_GPU_TRACE=T[,S[,N]]` -- T s after the first frame, N frames
  (default 3, 60 s apart) are traced encoder by encoder (`[gpu-trace] F<n>`):
  render passes (attachments with Metal pixel format, size, load/store, draw
  count, fragment functions `ps_<sha8>_...`, `uav:` = writable pixel-shader
  resources, `HAZARD` when an attachment is also a shader resource), compute
  dispatches (`shader_<sha8>`, grid, threadgroup size, newly resident
  textures/buffers with r/w; `HAZARD` when one texture is resident read-only
  and writable for one dispatch), blits; then the contents of every tracked
  float texture (count, NaN, Inf, zero, 1.0, 32.0, min/max/mean per channel,
  last row/column means, tiny levels' values, small grids row by row, larger
  levels as a 16x9 map). Every compute and pixel shader the traced frame uses
  is written to `Documents/shader-dump` (airconv keeps a registry of live
  shaders while the switch is set). Every S s (default 2, for 15 min) the small
  targets' statistics (`[gpu-val]`). `[rb-src]` names the source buffer of
  each distinct small readback (are the exposure spikes another buffer?).
  Tracked: 2D R32F/RG32F/RGBA32F up to 2048x2048, small R16F/RG16F/RGBA16F
  (<= 4096 texels), R32Uint <= 65536 texels; at most 64 textures / 160 MB,
  retained for the session. Cost: a few ms GPU wait per value dump.
* `MADEIRA_BORDER=black` -- samplers DXMT gave the white border (its stand-in
  for (32,32,32,32)) get transparent black. `[border]` lists such samplers.
* `MADEIRA_RP_LOAD=1` -- render-pass attachments never load or store
  DontCare (memoryless and resolve untouched). Correct, only slower.

Also: `tests/host/check-dxmt-patch-chain.py` (all 21 workflow patch scripts in
order on an unpatched dxmt, twice, plus the hooks), `tools/host-airconv.sh`
(host airconv + vkd3d-compiler, 5).

## 5. Host verification done here

* Full chain (21 scripts, workflow order) on a fresh copy of the pinned
  dxmt/src with build/madeira_cfg.h and research/remote-metal, twice: applies,
  idempotent (`DXMT_SRC_DIR=... python3 tests/host/check-dxmt-patch-chain.py`
  -> PASS).
* airconv built for the host against LLVM 15.0.6 (all patches, the same
  sources CI compiles; host-only `0ull` fix and stub Metal helper libraries),
  linked as `airconv` CLI. Test shaders compiled from HLSL with vkd3d-compiler
  2.0 (a luminance-style compute shader with a warp-synchronous tail,
  GroupMemoryBarrier, InterlockedMax on a RWTexture2D, InterlockedAdd on a
  RWBuffer, Buffer<> loads, SampleLevel, GetDimensions; a pixel shader with
  SampleLevel/Sample/log2/exp2/rsqrt): every switch alone and all together
  convert, the LLVM 15 verifier accepts the IR, and the IR shows exactly the
  intended change (simdgroup barriers after the tail's stores, guarded
  atomics with a phi, typed-buffer range checks, resinfo mip check, sample_l
  LOD + bias, no `air.fast_*`). With no switch the IR is byte-identical to the
  converter without this patch.
* `MADEIRA_SHADER_DUMP`: file names equal `sha1sum` of the bytecode; type and
  prefix filters work; the frame-trace registry dumps a live shader once,
  answers 0 the second time, -1 after SM50Destroy.
* The Objective-C of the trace patch (helper block and every inserted call
  site, in a context with winemetal_unix.c's variable names and winemetal.h's
  real structs) passes `clang -fsyntax-only -Wall` against minimal Metal
  declarations; the half-float decoder matches Python on all 65536 values; the
  statistics code runs on synthetic grids (row dumps, 16x9 maps).
* Not done here: an iOS compile (no Apple SDK) -- CI is the first real
  compile of winemetal_unix.c with these hooks.

## 6. Device test plan (one session)

Game file of God of War (Library -> long press -> Game settings -> Advanced),
one block per launch; keep the existing lines (`dxmt = d3d11.mipClampBC=2`,
swap, ...). In every launch: **stay in the title menu 30 s without touching
anything**, then Continue, walk out where the sky is in view and play 3
minutes. Send the log (`Documents/logs/GoW.exe-...txt`) and, for runs 1-2, a
zip of `Documents/shader-dump`. MetalFX off, FSR off unless stated.

1. **Diagnostics, 1280x720 native** (display resolution 1280x720):
   `env.MADEIRA_GPU_TRACE = 45,2,4` -- traces at 45 s (still in the menu),
   105, 165, 225 s.
2. **Reference, 1920x1080 native**: `env.MADEIRA_GPU_TRACE = 45,2,4`.
3. 1280x720: `env.MADEIRA_BORDER = black` (no shader re-conversion).
4. 1280x720: `env.MADEIRA_RP_LOAD = 1` (no re-conversion).
5. 1280x720: `env.MADEIRA_TGSM_SYNC = 1` and `env.MADEIRA_BOUNDS_EXTRA = 1`
   (re-converts shaders: the first loading takes longer).
6. 1280x720: `env.MADEIRA_PRECISE_MATH = 1` (re-converts).
7. 1920x1080 output with FSR 2 Balanced: `env.MADEIRA_SAMPLE_L_BIAS = 1`
   (re-converts).

If a run fixes it: repeat it at 1920x1080 native (no regression: the menu
must still read about 4.37 / 4460 and the picture must look as before) and,
for run 5, split the two switches. The M1 iPad user can run 1 and 5 at his
640x480.

Log lines that answer the question:
* every run: `[rb-buf] madeira-bcd value 16 bytes -> x e z w` while in the
  menu (e = 0.0175): the fix makes x/z match run 2's (~4.37 / ~4460);
  outdoors no single-frame jumps of x by ~5 followed by e falling.
* run 1/2: `[gpu-trace] F...` (the frame), `[gpu-trace] t=... #k t.....`
  with `row`/`map` lines (where the luminance values are and are not),
  `[gpu-val]` (the same over time, to catch a darkening wave), `HAZARD`,
  `uav:`, `[rb-src]`, `[border]`, `[shader-dump]`.
* switch confirmations: `[gow-exp]`, `[tgsm-sync]`, `[border] ... -> black`,
  `[rp-load]`, `[ld-bounds] ... on`, `[madeira-env] game MADEIRA_...`.

## 7. Analysing the results / what next

* Build the host tools: `tools/host-airconv.sh` (needs the dxmt submodule or
  `DXMT_SRC_DIR`; downloads LLVM 15.0.6 and vkd3d-compiler 2.0 into
  `~/.cache/madeira-host-airconv`). Disassemble a dumped shader with
  `vkd3d-compiler -x dxbc-tpf -b d3d-asm X.cs.dxbc`; convert it as the device
  does (with any `MADEIRA_*` switch in the environment) with `airconv -S`.
  Never commit game shaders.
* Map the trace: the luminance chain is the sequence of dispatches/passes
  touching the R32F/RGBA32F targets (ids `t.....` from the `tracking texture`
  lines); compare run 1 with run 2 dispatch by dispatch (grid, threadgroup,
  inputs) and the `row`/`map` dumps of each target (a target only partly
  written, values pinned at 1.0 or 0, NaN).
* If a PE-side cause is confirmed (border color, hazard nulling, UAV
  unbinding), the fix needs a `d3d11.dll` built from source: CI already
  builds DXMT's nvapi64.dll for arm64ec with llvm-mingw
  (`tools/build-dxmt-nvapi.sh`), so building `d3d11.dll` the same way from the
  pinned dxmt (plus the upstream hazard commits, or a border-color channel in
  the sampler argument entry that airconv's sample paths read) is possible,
  but it replaces upstream's committed binary for every 64-bit D3D11 game --
  a separate project for the owner's decision.

## 8. For HANDOFF (main session)

GoW below-1080p darkening (agent, 2026-10-01, docs/gow-darkening.md): the
menu's exposure readback differs by internal resolution (1080p x 4.37/z 4460,
720p 2.26/3120, 754x424 -0.84/1095), so the luminance chain's input is wrong
below 1080p; root cause not proven. New, all off by default (1080p unchanged;
shader cache salt unchanged without switches): tools/patch-airconv-gow-
experiments.py (MADEIRA_TGSM_SYNC, _SAMPLE_L_BIAS, _PRECISE_MATH,
_BOUNDS_EXTRA, _SHADER_DUMP), tools/patch-winemetal-gpu-trace.py
(MADEIRA_GPU_TRACE frame trace + float-target values + shader dump of the
traced frame, MADEIRA_BORDER=black, MADEIRA_RP_LOAD=1, `[border]`,
`[rb-src]`), two CI steps after "Patch winemetal GPU timeline for [frame]",
tests/host/check-dxmt-patch-chain.py, tools/host-airconv.sh. Waiting on the
device session of section 6.
