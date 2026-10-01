# Ghost of Tsushima: the "objelerdeki sıkıntı" (smoke squares), 2026-10-01

## Özet (sahibi için, Türkçe)

* **Gördüğün bozulma, dumanın kare kare çizilmesi.** 10-01 videosunda (build
  296, FSR kapalı, 1280x720) ateşin üstündeki duman parçacıkları yumuşak bulut
  yerine **keskin kenarlı, yarı saydam, içi düz koyu kareler** olarak çiziliyor:
  her biri döndürülmüş bir parçacık dörtgeni (oyun pikselinde ~40-150 piksel),
  dumanla birlikte hareket ediyor, üst üste binenler daha da koyulaşıyor. 4x4 /
  8x8 blok değil; BC doku çözme, karo (tile) hesaplama ya da dalga (wave) hatası
  bu şekli vermez. FSR açıkken aynı kareler FSR'ın zamansal toplaması yüzünden
  yuvarlak lekelere / sürtmelere dönüşüyordu (09-28 20:36 videosunda da aynı
  kareler var, sadece kenarları tırtıklı).
* **Kaynak neredeyse kesin: aydınlatılmış duman geçişi** (`ls_SetColor` +
  `ps_SetColor_MultiLight`). Bu geçiş DXIL tessellation ile çiziliyor (Apple'ın
  dönüştürücüsünün tessellation emülasyonu, build 199/211/213). Build 208-210'da
  bu çizimler hiç çizilmiyordu (log: `L4436=2696` atlandı) ve 210 videosunda
  aynı köprü/ateş sahnesinde **hiç kare yok**; 211'den beri çiziliyorlar ve ilk
  sonraki videodan (09-28 20:36) beri kareler var. Diğer parçacık geçişleri
  (ateş, kıvılcım, saydamlık) düzgün. Videodaki objeler (karakter, kaya,
  araba, zemin) normal görünüyor; başka bir objede bozulma görürsen o anda CAP'e
  bas, ayrı bakarız.
* **Henüz düzeltme yok, ama ayırt edecek anahtarlar hazır.** Hiçbiri
  varsayılanı değiştirmiyor; God of War'a dokunmuyor. Üç test **yeni build
  gerektirmeden 296 ile** yapılabilir (oyunun ayar dosyasına tek satır):
  `dxil-tess = 0`, `dxil-tess-max-factor = 0`, `msc-sample-nan-zero = 0`.
  Yeni build ile gelenler: `skip-ps` + `skip-ps-cycle` (tek oturumda, tek
  ekran kaydıyla hangi geçişin kare çizdiğini gösterir), `dxil-dump`
  (gölgelendiricilerin DXIL kodunu loga yazar), CAP + `capture-ps` artık DXIL
  çizimlerinin doku/örnekleyici bağlarını da yazıyor, ve deneme
  `dxil-tess-patch-topology = 1`.
* Test planı aşağıda (bölüm 6): her blok ayrı bir açılış, satırları oyunun
  dosyasına yaz, oyna, ateşe bak, logu (ve istenen yerde ekran kaydını / CAP
  klasörünü) gönder, sonra satırı sil.

## 1. Evidence used

| file | build / settings (from its header) | what it shows |
|---|---|---|
| `c15133c3-GhostOfTsushima.exe-2026-10-01_20-26-49.txt` (94,692 lines) | `[build] v0.1.296` (l.12), pack 6 not used (l.27), `library launch ... nvidia=1 game-config=0 metalfx=off` (l.28), `[display-shape] resolution=1280x720` (l.35) | the session of the video; ends 20:40:45 |
| `cd56699d-ScreenRecording_10-01-2026_20-40-37_1.mp4` (5.3 s) | same session (HUD: 1280x720, 3.0x, frame 20957-21030, 16.6-17.5 FPS), FSR off (owner) | the squares |
| `9774461a-ScreenRecording_09-28-2026_20-36-41_1.mp4` | IPA 218 + pack 5, log `48e06b1e-...09-28_20-35-31` (`DXIL tessellation: 3306 drawn (3306 indirect)`, l.61460), FSR on | same squares, jagged |
| `7fe046c7-8D134DA3-...mov` (09-28 10:17 local) | build 210 test (log `20f3dfa1-...09-28_10-13-47`: `skips by site: L4436=2696`, l.47485) | same bridge/fire, **no squares** |
| `d5251b3b`, `a8dbb388`, `edc98e2a`, `fc640b72` `-image.png` | build 209/210 screenshots (1564x720) | soft haze, yellow smears (the RGBA32-clear bug fixed in 210), no squares |
| `290398ae-...09-28_13-21-19.txt` | build 211 | `DXIL tessellation: 3117 drawn (3117 indirect)` (l.46464): the lit particles are drawn from here on |
| scratch `cap203/f6858`, `f6938`, `f7453` contact sheets | build 203 CAPs (an earlier session) | particle passes exist (512x512 R16F light-view opacity, 400x300 R16F screen transmittance); no smoke on screen in those frames |

Frames were extracted with ffmpeg (imageio-ffmpeg wheel, host only) at 2 and
10 fps and at full resolution (2868x1320; the 1280x720 game image spans
x = 262..2606, so one game pixel is ~1.83 recording pixels).

## 2. The artefact

`cd56699d` (build 296, FSR off), every frame from t = 0.0 s to 5.3 s:

* **Shape:** squares, each rotated at its own angle -- particle billboards.
  Side length ~75-260 recording pixels = **~40-150 game pixels**. Crisp,
  straight edges at game resolution. Not a grid, not 4x4/8x8/16x16 blocks, not
  screen-aligned.
* **Content:** uniform inside -- no smoke texture, no soft falloff to the
  edges. Translucent (the fire glow, the pole and the bridge show through),
  darker than the sky; where squares overlap the overlap is darker
  (multiplicative / alpha stacking). The squares near the fire take a little
  of its colour.
* **Where:** only in the smoke column over the burning bridge / wreck
  (t = 0.0 s `f_0001`, t = 0.4 s, t = 1.5 s, t = 3.0 s, t = 4.5 s). The fire
  itself, the flames on the wreck and the embers (small white dots) are soft and
  correct. The character, the rock, the cart, the ground look normal (some
  stair-stepping on the burning debris edges, consistent with the game's
  reduced-resolution transparency).
* **Motion:** the squares rise and move with the smoke between frames; the
  set changes every frame (particles), camera-independent in shape.
* **With FSR on** (09-28 20:36:41, `9774461a`, t = 3 s): the same dark rotated
  squares over the sky right of the bridge, with jagged pixelated edges
  (upscaled from ~640x360) and temporal smearing -- the owner's "more rounded"
  artefacts and the earlier "specks / smears".
* **Before the lit-particle draws existed** (build 210 video `7fe046c7`, same
  place, t = 0-8 s): no squares; smoke is a soft haze.

## 3. How the smoke is drawn (10-01 log)

At 20:27:32 the session rendered at 640x360 internal (FSR performance before
the owner switched it off); the draw-dump of one frame (l.24133-24257):

| l. | pass | target | blend |
|---|---|---|---|
| 24135 | `vs_SetColor` / `ps_SetColor`, ExecuteIndirect, triangle strip | 512x512 R16F (dx54), no depth | src DEST_COLOR, dst ZERO: a multiplicative opacity map (probably the light's view, for smoke shadows) |
| 24169 | `vs_SetColorCombinedAlpha` / `ps_SetColorCombinedAlpha`, ExecuteIndirect | 320x180 R16F + 320x180 D32 (GREATER_EQUAL, no write) | dst x (1 - src): screen transmittance |
| 24171 | **`ls_SetColor` / `ps_SetColor_MultiLight`**, ExecuteIndirect, **topology 36 (4-control-point patches)** | **the scene HDR target itself** (640x360 RGBA16F dx10 + its D32S8 depth, GREATER_EQUAL, no write) | **src ONE, dst INV_SRC_ALPHA (premultiplied), RGB only** |

The same particle set goes through all three (`[probe]`: 4 vertices x N
instances, the same N in the three passes, e.g. l.25233 `4 18`, l.28999
`4 1650`, l.49855 `4 5270`). The third pass blends the lit smoke straight onto
the scene: a pixel shader that returns the right colour but a **constant alpha
over the whole quad** darkens the scene in exactly these uniform squares.

The lit pass is a DXIL tessellation pipeline: l.12091 `DXIL tessellation through
the converter's emulation: on`, l.12169 `factor cap: 3 for pipelines declaring
<= 16`, l.12170 `vs 'ls_SetColor', 4 control points in, 4 out (64 B), 32
patches x 4 threads ..., output primitive 4, max factor 9.0, vertex 32 B`,
l.12184 `[winemetal] DXIL tessellation pipeline OK: vs 'ls_SetColor' mesh
'irconverter_domain_shader_triangle_passthrough' ps 'ps_SetColor_MultiLight' ...
max factor 3.0`; one more variant stays a placeholder (l.12177 `domain
reflection not usable`). Final count in this run: `DXIL tessellation: 15460
drawn (15460 indirect)`.

## 4. Ranked causes

1. **The lit-smoke pass (`ls_SetColor` + `ps_SetColor_MultiLight`) through
   the DXIL tessellation emulation loses the per-pixel opacity.** Evidence:
   the footprint is whole particle quads; builds 208-210 skipped exactly these
   indirect tessellation draws (`indirect draw on a geometry-shader pipeline is
   not implemented`, l.29605 of the 10:13 log; `L4436=2696`) and the 210 video
   has no squares at the same spot; 211 drew them (3117), every later video has
   the squares; the two non-tessellated particle passes were drawn in 210 as
   well. What inside the path, in order of likelihood:
   * 1a. the domain-shader output that carries the particle UV / opacity does
     not reach the pixel shader intact (the converter's mesh passthrough, or
     NaN UVs that `msc-sample-nan-zero` (build 217) now flushes to 0 -- a
     constant UV gives exactly a uniform quad). Supporting, not conclusive:
     with 211/212 (lit particles drawn, no flush yet) the owner reported dark
     specks on the fire-lit smoke that "come and go between frames" (HANDOFF,
     build 217), i.e. what undefined NaN-coordinate samples look like; the
     first video after 217 shows uniform squares instead. Specks were also
     reported with 209/210, so part of that was something else (the uncleared
     RGBA32 target fixed in 210). Block C tests this directly;
   * 1b. the tessellation factor cap (build 213, factor 9 -> 3), if the domain
     shader derives anything from the factors;
   * 1c. the stages are converted with `IRInputTopologyTriangle`: the service
     maps every topology type that is not point or line to triangle, PATCH (4)
     included, although the converter has `IRInputTopologyPatch`
     (`ir_input_topology.h`). Apple's documentation does not say what it changes
     for tessellation; cheap to try;
   * 1d. wrong fragment-stage binding (texture / sampler) in the mesh pipeline
     -- the bindings are the same top-level buffers as for plain draws, so less
     likely.
2. **Texture contents of the smoke sprite (placed / heap-aliased streaming
   textures).** GoT does place its textures (6000 `[placed]` lines, heap flags
   0x44): the streamer keeps 64x64-and-smaller tails in 32 MB heaps of 64 KB
   slots (heaps 225-234, 512 placements each, every Metal size <= 64 KB). Only
   one placement overlaps its neighbour (heap5, r#766 256x256 BC3, Metal size
   96 KB, placed 64 KB before r#325) -- worth a look, but a content problem
   would also show in the non-tessellated passes that use the same sprites, and
   the timeline points at the tessellated pass.
3. **Not the cause, by evidence:**
   * BC decode: the D3D12 runtime maps BC1-BC7 to Metal's own BC formats
     (`mad_map_texture_format`); nothing decodes BC on the CPU, and the
     footprint is not 4x4.
   * `ResourceMinLODClamp` folding (ml1089): GoT creates none (l.15611 `SRVs
     with a min-LOD clamp folded into the view: 0`).
   * ExecuteIndirect: only single-argument signatures (l.10870-10872), no count
     buffers.
   * GPU faults / skipped work: `0 ENDED IN ERROR`, `skips by site: none`
     throughout; the `GPU fault shader` lines (l.12520 ...) are hashes kept in
     `C:\madeira-cs\fault-shaders.txt` by earlier runs, logged only.
   * Tile/wave/groupshared compute, D32S8 planes (build 193), render-pass load
     actions (always Load/Store), missing clears: none of them gives rotated
     particle-shaped squares that appear exactly when one pass is drawn.
   * Sampler LOD bias: the game's samplers carry -2.0 (l.15410, sharper, not
     uniform).

## 5. What changed (code)

All in the D3D12 runtime (`madeira-d3d12`), so God of War (D3D11 through DXMT)
cannot see any of it; every switch is OFF unless written in madeira.cfg or the
game's file, and each is read once and logged when set.

* `skip-ps = <entry>[,<entry>...]`, `skip-ps-cycle = <seconds>`
  (`madeira_d3d12.c`, `mad_skip_ps_load` / `mad_skip_ps_match`, hook in
  `exec_draw` after the render pass began, so clears still run): draws whose
  pixel OR vertex entry is listed (exact names) are dropped and counted in
  `skips by site`. With a cycle, phase 0 skips nothing, phase k only the k-th
  name, N seconds each, round and round; `[skip-ps] phase k/n from present #P
  (t+S s): skipping 'X'` marks every change, so one screen recording with the
  HUD frame counter attributes the squares to a pass.
* `dxil-dump = <entry>[,<entry>...]` (`mad_dxil_dump_wanted` /
  `mad_dxil_dump_one`): a pipeline whose VS, PS or CS entry is listed gets the
  bytecode of every stage it has (vs, hs, ds, gs, ps / cs) written to the log
  (`[dxil-dump] <stage> of '<entry>' <hash>: N bytes follow as base64`, then
  `[b64 <hash>]` lines, the GPU-fault format) and to
  `C:\madeira-cs\dump_<stage>_<entry>_<hash>.dxil`; each bytecode once, at most
  48 blobs / 3 MB. Disassemble with HANDOFF section 5's recipe
  (`tools/dxil-disasm.py`). Hull and domain entries are reported by the
  converter as `irconverter_hull_shader` / `irconverter_dxil_domain_shader`,
  hence the match on the pipeline's VS/PS names.
* `capture-ps` now covers converter (DXIL) draws: the targeted draw capture
  walked only the airconv range list, which is empty for DXIL pipelines, so a
  CAP with `capture-ps` showed GoT's vertex/index buffers and nothing else. The
  root-signature walk of `capture-cs` (ml1141) is now shared
  (`mad_capture_rs_tables`, log tag `capture-draw`; `capture-cs` output is
  unchanged): root constants, root CBV/SRV/UAV, every descriptor-table entry
  with the texture's size, format, mips, the view's mips/slice/format/swizzle
  and min-LOD word, buffers with size and offset, the first 1 KB of each CBV,
  the SRV textures copied raw (`Documents/capture/*_tex*.raw`, BC included),
  and now every **sampler's state** (filter, address modes, LOD range, bias,
  anisotropy, compare, border -- a small table filled at CreateSampler and for
  static samplers, `mad_smpdesc_*`) plus the root signature's static samplers.
  A first line says whether the pipeline is a DXIL tessellation one and its
  factor. `capture-ps` names now match exactly (`mad_name_in_list`): the old
  substring test made `ps_SetColor` match a list holding
  `ps_SetColor_MultiLight`, and its 512x512 pass, which runs first, would have
  used up the 8 shots.
* `dxil-tess-patch-topology = 1` (experiment; `mad_dtess_topology`,
  `MADEIRA_IR_TOPOLOGY_PATCH_STRICT` in `madeira_ir_abi.h`, mapping in
  `madeira_ir_unix.mm`): the VS/HS/DS of a DXIL tessellation pipeline are
  converted with `IRInputTopologyPatch` instead of `IRInputTopologyTriangle`.
  The value differs, so both shader caches (PE `mad_sc`, unix `madeira_dxil_cache.h`)
  keep the two conversions apart; the geometry-shader path and every other
  pipeline are untouched. Native change: needs an IPA.
* Housekeeping: the base64 writer of the GPU-fault shaders is shared
  (`mad_log_b64`, same output); `MAD_SWZ_IDENTITY` moved to the top.
* `app/Madeira/ConfigCatalog.generated.swift` regenerated (four new keys).
* `tests/host/check-got-diagnostics.py`: static checks (defaults, hook
  placement, cache keys, capture-cs tag) and a host-compiled harness that runs
  the cut-out `skip-ps` / `skip-ps-cycle` / `dxil-dump` parsers (unset, exact
  names, rotation with a fake clock).

Host verification: the runtime compiles and links for arm64ec with
llvm-mingw 20260421 against a patched DXMT tree (only the four pre-existing
unused-function warnings); `check-got-diagnostics.py` PASS;
`check-dxmt-patch-chain.py` PASS (with `DXMT_SRC_DIR` pointing at the main
checkout's dxmt); the catalog generator, run with the main checkout's
submodules, reports `current` after the regeneration (in this worktree the
submodules are not checked out, so `check-config-catalog.py`'s generator step
fails here exactly as it did before the change). `madeira_ir_unix.mm` only
compiles in CI.

Cost notes: the native ABI changes (unix side, ABI header, app catalog), so
this ships in an IPA, not a pack. The shader-cache converter identity hashes
`madeira-d3d12/src/unix` and the ABI header, so GoT converts its shaders once
on the first launch of that IPA (the airconv experiment patch already changed
that identity for the next build anyway).

## 6. Device test plan

Oyunun dosyası: kütüphanede Ghost of Tsushima → oyun ayarları →
"Advanced: this game's config". Her blok **ayrı bir açılış**; satırları yaz,
"Save and play", ateşli köprüye / dumana bak, en az 20-30 saniye oyna, çık,
logu gönder, sonra satırları sil. F0 kullanma. FSR kapalı kalsın (kareler
öyle daha net). Blok 0, A, B ve C **296 ile, yeni build beklemeden**
yapılabilir; D, E ve F bu değişiklikleri taşıyan bir sonraki IPA'yı ister.

**Blok 0 -- CAP (296, satır yok).** Dumanda kareler görünürken CAP'e bas.
`Documents/capture/` klasörünü (sheet PNG'leri + index) ve logu gönder.
Logda: `[capture] ===== capturing frame N` ve `[capture-sheet]` satırları (her
küçük resmin geçişi, `last ps ...` alanıyla). Bakılacak: karelerin ilk göründüğü küçük resim
(sahne HDR hedefi, `ps_SetColor_MultiLight` geçişinden sonra mı?).

**Blok A (296):**
```
dxil-tess = 0
```
Log: `DXIL tessellation through the converter's emulation: off`. Ekran:
beklenen **kareler yok** (aydınlatılmış duman ve su da yok). Kareler hâlâ
varsa 1. sıradaki neden yanlış: Blok D'ye geç.

**Blok B (296):**
```
dxil-tess-max-factor = 0
```
(oyun sayfasındaki "tessellation cap" seçicisi de olur). Log: `DXIL
tessellation factor cap: 0`. Ekran: kareler yumuşak dumana dönerse sebep
build 213'ün faktör sınırı (1b); FPS düşebilir (parçacık sayısıyla GPU süresi
artıyordu).

**Blok C (296):**
```
msc-sample-nan-zero = 0
```
Uyarı: bu anahtar gölgelendirici önbelleğinin kimliğini değiştirir ve diğer
önbellek klasörleri silinir (`mad_sc_prune`). İlk açılışta "Compiling
shaders" birkaç dakika sürer (hepsi yeniden çevrilir); satırı sildikten
sonraki ilk açılış da bir kez daha uzun sürer. Bu yüzden bu blok A ve B'den
sonra, sadece gerekiyorsa. Log: `[madeira-ir] MSC
4.0.1 compatibility: ... sampled NaN -> 0 off`. Ekran: kareler başka bir şeye
(benekler, çöp, renkli lekeler) dönüşürse duman pikselinin UV'si NaN geliyor
demektir (1a) → Blok E ile kodu okuruz.

**Blok D (yeni build), tek oturumda hangi geçiş:**
```
skip-ps = ps_SetColor_MultiLight,ps_SetColorCombinedAlpha,ps_SetColor
skip-ps-cycle = 8
```
Ateşe bakarken **ekran kaydı al, en az 40 saniye** (HUD'daki Frame sayacı
görünsün). Log: `[skip-ps] madeira-bcd DIAGNOSTIC: 3 shader name(s)` ve her 8
saniyede bir `[skip-ps] phase k/3 from present #P (t+S s): ...`. Faz 0 hiçbir
şeyi atlamaz, faz 1 yalnız `ps_SetColor_MultiLight`, faz 2 yalnız
`ps_SetColorCombinedAlpha`, faz 3 yalnız `ps_SetColor`. Beklenen: kareler
**yalnız faz 1'de** kaybolur. (Not: `ps_SetColor` arayüzde de kullanılıyor;
faz 3'te bazı HUD öğeleri kaybolabilir, normal.)

**Blok E (yeni build), kodu ve bağları oku:**
```
dxil-dump = ls_SetColor,vs_SetColorCombinedAlpha,vs_SetColor
capture-ps = ps_SetColor_MultiLight
```
(`capture-ps` en fazla 8 çizim yakalar ve her ExecuteIndirect kaydı ayrı bir
çizim sayılır; bu yüzden yalnız baş şüpheli. Gerekirse sonraki açılışta
`capture-ps = ps_SetColorCombinedAlpha`.)
Duman görünürken CAP'e bas. Log: `[dxil-dump] vs of 'ls_SetColor' ...`, `hs`,
`ds`, `ps` satırları ve `[b64 ...]` blokları; `[capture-draw] converter
pipeline: ... DXIL tessellation ...`, ardından `[capture-draw] pN SRV tK
...` (doku boyutu/biçimi/mip/swizzle), `[capture-draw] ... sampler ... filter
... LOD ...`, `static sampler` satırları. Logu ve `Documents/capture/`
klasörünün tamamını (raw dosyalar dahil, zip) gönder.

**Blok F (yeni build), deneme:**
```
dxil-tess-patch-topology = 1
```
Log: `DXIL tessellation stages converted with the converter's PATCH input
topology`, sonra `[winemetal] DXIL tessellation pipeline OK` (ya da
`REFUSED` / `not usable` -- o da bilgi). İlk açılışta su ve parçacık
pipeline'ları yeniden çevrilir. Ekran: kareler gidip duman yumuşadıysa sebep
1c; su da düzgün mü bak.

### Reading the results (for the next agent)

| result | meaning | next step |
|---|---|---|
| A: squares gone | the tessellated lit pass draws them | B/C/F decide the sub-cause |
| B: soft smoke | the factor cap breaks the domain shader | keep the cap off for `ls_SetColor` (or raise it to the declared 9), measure GPU time |
| C: squares turn into specks/garbage | NaN UVs in the tessellated path | read the DS/PS from Block E's dump: which DS output carries the UV, which PS input reads it |
| D: squares only gone in phase 1 | confirms the lit pass alone | -- |
| E | the DS/PS DXIL and the PS's real texture/sampler | disassemble (`tools/dxil-disasm.py`), decode the raw sprite (`pip install texture2ddecoder` on the host for BC) |
| F: soft smoke | wrong input topology for tessellation conversions | make it the default after a water check |

## 7. Paragraph for HANDOFF (ready to paste)

* **GoT "objelerdeki sıkıntı" = smoke squares (agent, 2026-10-01; docs/got-corruption.md).**
  Video `ScreenRecording_10-01-2026_20-40-37` (build 296, FSR off, 1280x720)
  and log `GhostOfTsushima.exe-2026-10-01_20-26-49`: the smoke over the burning
  bridge is drawn as hard-edged, uniformly translucent dark ROTATED SQUARES
  (one per particle, ~40-150 game px), not 4x4/8x8 blocks; FSR only smeared
  them (09-28 20:36 video shows the same squares). Timeline: builds 208-210
  skipped the indirect DXIL-tessellation draws (`L4436=2696`) and the 210 video
  at the same spot has none; 211 draws them (`ls_SetColor` /
  `ps_SetColor_MultiLight`, premultiplied straight onto the scene HDR target)
  and every later video has the squares. Prime suspect: the lit-smoke pass in
  the converter's tessellation emulation loses the per-pixel opacity (UV not
  reaching the PS / NaN UV flushed by msc-sample-nan-zero / factor cap 3 /
  triangle instead of patch input topology). Ruled out with log evidence: BC
  decode (native BC formats), min-LOD clamp (0 SRVs), multi-arg ExecuteIndirect
  and count buffers, GPU faults/skips, LOD bias. **Added, all OFF by default,
  D3D12 runtime only (God of War untouched):** `skip-ps` + `skip-ps-cycle`
  (drop / rotate draws by shader name, `[skip-ps] phase` lines),
  `dxil-dump` (every stage's bytecode of named pipelines to the log as
  `[b64 <hash>]` and `C:\madeira-cs\dump_*.dxil`), `capture-ps` now walks DXIL
  draws' root signatures (`[capture-draw]` textures, views, sampler states,
  static samplers, raw sprite copies; capture-ps names now exact),
  `dxil-tess-patch-topology = 1`
  (IRInputTopologyPatch for tessellation stages; native, needs an IPA; cache
  keyed apart). Catalog regenerated; `tests/host/check-got-diagnostics.py`
  PASS; runtime builds for arm64ec locally. **Device plan** (docs/got-corruption.md
  section 6): on 296 without a build: CAP; `dxil-tess = 0`;
  `dxil-tess-max-factor = 0`; `msc-sample-nan-zero = 0`; after the next IPA:
  `skip-ps-cycle` run with a screen recording, `dxil-dump` + `capture-ps` + CAP,
  `dxil-tess-patch-topology = 1`. Open: the actual fix depends on which block
  removes the squares.
