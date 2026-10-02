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
* **Güncelleme (aynı gece, build 303):** `dxil-tess = 0` kareleri kaldırdı.
  Kalan "havada şekiller" (tek karelik, yanlış yerde kaya / sürtme izleri)
  bölüm 8'de: kare kare inceleme, nedenler, yeni tanı anahtarları ve yeni test
  planı (G1 ve G2 yeni build beklemeden).
* **Güncelleme 2 (10-02, build 313):** G1, G2 ve H şekilleri kaldırmadı;
  bölüm 9: yeni ölçüm kapsamı, yeni deneme düzeltmesi ve 3 açılışlık plan.

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

## 8. One-frame shapes after `dxil-tess = 0` (build 303, 2026-10-01 21:30)

### 8.0 Özet (sahibi için, Türkçe)

* **Kareler gitti, `dxil-tess = 0` bunu kanıtladı:** duman kareleri DXIL
  tessellation ile çizilen aydınlatılmış duman geçişiydi (bölüm 4'ün 1.
  sırası). Bu satır şimdilik oyun dosyasında kalsın.
* **"Havada oluşan anlamsız şekiller" kare kare:** 21:33 kaydının oyun
  kısmında (0-5.2 s) **en az 12 bozuk kare** var, yani kabaca her 6-8 oyun
  karesinden biri. Bozukluk **tek kare** sürüyor; bir önceki ve bir sonraki
  kare temiz (bazen iki ardışık kare, iki farklı bozuklukla). Üç tür:
  1. **Koyu bir kaya** yanlış yerde: köprünün önünde arabayı örten dev kaya
     (4.67 s, fenerin ışığı üstünde parlıyor), arabanın önünde (2.80 s, 4.92
     s), yerde ölü düşmanın yanında (3.93 s), hatta **gökyüzünde uçan** küçük
     bir kaya (1.37 s).
  2. **Sürtme / iz**: köprü tahtaları ya da bir ağaç tepesi, hareket
     bulanıklığıyla çekilmiş gibi sarı-turuncu dikey/çapraz izler (1.32, 1.97,
     2.78, 3.53, 3.98, 4.87 s).
  3. Bir kare boyunca **mavi ay ışığı**: soldaki kaya yüzü ve karakterin
     zırhı mavi aydınlanıyor (0.92 s).
  Kamera neredeyse sabitken de oluyor; HUD'daki kare süresi grafiğindeki
  sıçramalarla eşleşmiyor.
* **Ne anlama geliyor:** objenin kendisi doğru (kaya kaya gibi görünüyor), ama
  o kare için **başka bir objenin ya da başka bir karenin konum verisini**
  okuyor: kaya başka bir objenin yerinde/boyutunda çiziliyor; hareket
  bulanıklığı bu yanlış konum ile önceki karenin konumu arasındaki farkı dev
  bir hız sanıp sürtüyor. Bu veriyi oyun her kare CPU'dan **UPLOAD
  belleğine** yazıyor (GoT'un 8-32 MB'lık 7 büyük upload tamponu var).
* **Madeira tarafında olası nedenler (sırayla):**
  1. **GPU bayat sayfa okuyor:** bu büyük upload tamponları Madeira'nın kendi
     belleğinde (ml1154, `upload-swap`) ve senin `swap-mb = 3072` ayarınla
     **dosya destekli takas belleğinde** duruyor; dosya neredeyse dolu (3069 /
     3072 MB), bellek baskısı yüksek (6.5 GB, 1.3 GB sıkıştırılmış). GPU'nun
     gördüğü sayfa CPU'nun son yazdığı olmayabilir.
  2. **Oyun veriyi GPU işini bitirmeden yeniden yazıyor** (çit erken "bitti"
     görünüyor). Kodda gerçek bir yarış penceresi var: Queue::Wait, başka bir
     iş parçacığının Signal'i "istendi" ama henüz Metal'e gönderilmedi iken
     geçebiliyor. Ayrıca "GPU seri N'ye ulaştı = N'ye kadar her şey bitti"
     varsayımı çit zincirine dayanıyor, kendiliğinden garanti değil.
  3. Bizim GPU içi sıralamamız (dolaylı argüman sondası `ind-probe` render
     geçişini bölüyor) -- zayıf aday: saniyede ~1 küme, bozukluklar daha sık.
  4. Descriptor yuvalarının GPU kullanırken yeniden yazılması.
* **Hazır olanlar:** `upload-swap = 0` ve `ind-probe = 0` **303/306'da
  zaten var** (yeni build beklemeden). Yeni build ile gelenler (hepsi
  varsayılan KAPALI, God of War'a dokunmaz): `fence-strict` (1/2),
  `upload-guard` (1/2, + `upload-guard-bytes`), `desc-guard`,
  `cbv-snapshot`. En değerlisi `upload-guard = 2`: **tek oturumda** 1 ile 2
  arasında karar verir (`CHANGED` = oyun erken yazdı; `GPU SAW DIFFERENT
  BYTES` = GPU bayat bellek gördü).
* Plan bölüm 8.6'da: her blok ayrı açılış, `dxil-tess = 0` her blokta kalsın,
  bozuklukların olduğu yerde (ateşli köprü) 30-60 sn oyna, ekran kaydı al,
  logu gönder, sonra bloğun diğer satırlarını sil.

### 8.1 Evidence

| file | build / settings | what it shows |
|---|---|---|
| `47955180-GhostOfTsushima.exe-2026-10-01_21-30-15.txt` (113,364 lines) | `[build] v0.1.303` (l.12); `library launch ... nvidia=1 game-config=1 metalfx=off` (l.21); `madeira.cfg: swap-mb=3072` (l.26); `[game-cfg] dxil-tess = 0` (l.163); 1280x720 | DXIL tessellation off (l.12878); `async-submit = 0` (l.9118); `fence-chain = 1` (l.10997); `upload-swap = 1` (l.10495) |
| `13fbab5d-ScreenRecording_10-01-2026_21-33-21_1.mp4` (7.8 s) | the same session, recorded from ~21:33:21 | gameplay 0-5.2 s, then Control Center |

Frames: all 200 native frames extracted with their pts (`ffmpeg -fps_mode
passthrough -frame_pts 1`); a one-frame transient detector (|frame -
mean(prev, next)| beyond what prev->next explains, over sky and bridge, HUD
and touch controls masked); every hit viewed as a prev/cur/next strip.

### 8.2 The artefact, frame by frame

Native frame index and time in the recording (the game runs at ~15-20 FPS, so
several recording frames show one game frame):

| frame | t (s) | what is wrong for ONE frame |
|---|---|---|
| #20 | 0.917 | a large rock face on the left lit by blue moonlight, blue rim light on Jin's armour and on the dead enemy |
| #29 | 1.317 | horizontal streaks across the bridge deck (motion-blur smear) |
| #30 | 1.367 | a small dark rock floating in the sky right of the lantern pole |
| #44 | 1.967 | a tall yellow-green streaked plume (a tree crown?) from the top of the frame down to the bridge; the right side of the bridge smeared |
| #62 | 2.783 | bridge planks smeared upward around the lantern |
| #63 | 2.800 | a dark boulder in front of the cart |
| #79 | 3.533 | a horizontal smear across the bridge deck |
| #87 | 3.933 | a dark rock body on the ground right of the cart, next to the dead enemy |
| #88 | 3.983 | the bridge smeared again |
| #102 | 4.667 | a huge dark rock over the bridge in front of the cart, lit by the lantern (specular spot) |
| #106 | 4.867 | a diagonal orange streak from the bridge upward |
| #107 | 4.917 | a dark rock with a fire-lit spot in front of the cart |

The parent's a008 (dark smudge over the cart) and a015/a016 (streaked
ellipses around the lanterns) are the same two kinds. Every broken frame is
followed by a clean one; the shapes neither persist nor grow. The HUD
frame-time graph shows no spike at #20 and only unrelated spikes elsewhere.

Reading: the meshes are right (the rock is a rock, textured, with the
lantern's specular on it); their **per-object data** is not: a rock drawn with
the transform of another instance or another frame (#30, #63, #87, #102,
#107); objects whose current and previous transforms disagree, which the
motion-blur pass turns into long streaks (#29, #44, #62, #79, #88, #106); once
the lighting / moon-shadow constants of another frame (#20). All of it is data
the game writes from the CPU every frame -- per-draw constants and per-instance
streams in UPLOAD memory -- and reads on the GPU in GoT's GPU-driven passes
(`vs_HighLod` / `vs_LowLod` / `vs_SetMaterial_*` ExecuteIndirect, instance
stream "vb 1: 16 MB, stride 8", section 3).

### 8.3 What the log says

* Submission per frame (l.50807, 21:33:24): `ExecuteCommandLists 9.0, Signal
  8.0, fence waits 1.1, GetCompletedValue polls 6.0, Queue::Wait sleeps 0.0`.
  Queues: DIRECT (l.9117), COMPUTE (l.9894), COPY x2 (l.9895, l.10516; one is
  destroyed). Queue::Wait never slept: either GoT issues no cross-queue Wait,
  or every one took the early return `f->submitted >= value` (see 8.4, cause
  2); the log cannot tell which.
* GPU health: `35543 retired, 0 ENDED IN ERROR` (l.50729); the encoder fence
  chain is complete (`807376 waits, 807376 updates`, l.50731); no GPU faults.
* Skips: `15 skipped` per 600 lists, all at one site (`L4653` in 303 = `draw
  without a pipeline state`): the tessellated smoke's placeholder pipeline,
  which is what `dxil-tess = 0` is meant to do.
* UPLOAD memory: `ml1154 CPU-visible buffers on file-backed storage: 8, 82 MB`
  (l.50616); at load 32 MB (l.10497), 8, 16, 12, 12 MB (l.10949-10981), 8 MB
  READBACK (l.11611), 10 and 8 MB (l.11797, l.11885): every large UPLOAD
  buffer of the game lives on Madeira's own storage, i.e. on the swap tier.
  Swap tier: `2888 MB file-backed now (peak 3022), 133 extents, file used 3069
  of 3072 MB, backs 76 releases 491 unbacks 0 refused 2` (l.50263). Footprint:
  `phys=6546 MB (peak 6575) ... compressed=1276 MB` (l.50790): heavy memory
  pressure.
* Render targets: each placed render target sits alone in its own heap at +0
  (`[placed] r#465..r#508 ... in heapNN ... at +0`), so render-target aliasing
  is **ruled out**.
* Placed small textures (heap5, 32 MB, flags 0x44): r#739 (256x256 BC3) went
  to +26148864, a 64 KB slot, but Metal needs 98304 bytes for it; it overlaps
  r#325's slot (+26214400) by 32 KB. That corrupts texture CONTENT (a patch of
  a texture), not geometry; a separate finding.
* ExecuteIndirect: only single-argument signatures (`stride 16/20/12`,
  l.10990-10992), no count buffers; culled records carry InstanceCount 0 (the
  probes show e.g. `vs_HighLod first record: 4836 0 40 0 0`), so "records past
  the count" is **ruled out**.
* Occlusion queries: `994 begun, 0 results delivered` (l.50730): GoT resolves
  into a GPU-only buffer, which we never write. Constant, not a flicker; noted.
* Indirect-argument probes (`ind-probe`, default ON): 1194 `[probe]` lines;
  clusters every ~3 s per pipeline group, i.e. roughly one probe frame a second
  (between the `[xp]` stamps 21:33:21.9-22.3, 22.3-22.8, 23.7-24.2, 25.0-25.4,
  25.4-26.1). Each probe ends the open render pass and runs one compute
  dispatch. The recording's start is only known to the second, so frames
  cannot be matched to probes; the shapes (2-3 a second) are more frequent
  than the probe frames.

### 8.4 Ranked causes

1. **The GPU reads UPLOAD pages that do not hold the CPU's latest writes
   (ml1154 storage on the swap tier).** All of GoT's large per-frame upload
   buffers are VirtualAlloc'd by us and handed to Metal as no-copy buffers;
   with `swap-mb = 3072` a >= 8 MB guest commit is file-backed, the file is
   full and the device is under pressure. If a page the GPU maps is not the
   page the CPU last wrote, the GPU reads an older packing of the game's ring:
   another object's instance index or transform -> a rock somewhere else, a
   plank with a wild velocity. Fits "one frame, random, always the same few
   kinds of object". Not proven (Metal may wire no-copy pages).
   Discriminators: `upload-swap = 0` (Metal-owned storage; available now) and
   `upload-guard = 2` (`GPU SAW DIFFERENT BYTES` with unchanged CPU bytes).
2. **The game rewrites upload data the GPU has not finished with (a fence or
   Wait that completes early).** One real window in the code: queue_Signal
   sets `fence->submitted` BEFORE its batch is committed (mad_signal_run
   flushes after), and the synchronous Queue::Wait returns as soon as
   `submitted >= value` -- a Wait on another thread can return and commit its
   own batch ahead of the signalling one. Second, "GPU event >= serial s" is
   taken to mean "every batch <= s finished"; that holds through the encoder
   fence chain, not by construction. Discriminators: `upload-guard`
   (`CHANGED` lines), `fence-strict = 1` (counts the Wait window, orders
   batches on the GPU), `fence-strict = 2` (no CPU/GPU overlap at all: if the
   shapes survive this, it is not a CPU/GPU race).
3. **GPU-internal ordering around work we insert ourselves** (indirect probe
   render-pass splits; the present copy outside the fence chain). Weak: too
   infrequent, and the passes it splits re-bind everything. Discriminators:
   `ind-probe = 0`, `fence-strict = 1`.
4. **Descriptor slots rewritten while a batch still uses them** (would rather
   show wrong textures or wrong structured buffers than wrong transforms).
   Discriminator: `desc-guard = 1`.

Ruled out above: render-target aliasing, count-buffer records, GPU faults,
dropped draws (only the smoke placeholder is skipped).

### 8.5 What changed (code)

`madeira-d3d12/src/pe/madeira_d3d12.c`: one block "SYNC DIAGNOSTICS" right
before `exec_arg_slot_for`, plus hooks; the keys are read once by
`mad_sync_diag_load`. With every key unset `g_sd_state` is 0, nothing below
runs and nothing is logged (every hook is `if (g_sd_state > 0 ...)`). D3D12
runtime only: God of War (D3D11/DXMT) never reaches it. One line when anything
is on: `[sync-diag] madeira-bcd DIAGNOSTIC: fence-strict=F upload-guard=U (B
bytes a range) desc-guard=D cbv-snapshot=S bytes`, and every 300 presents
`[sync-diag] present #N: upload-guard ... ranges noted, ... checked, ...
CHANGED while in flight (+... in approximate windows; ...), ... copied by the
GPU, ... of them DIFFERENT from the CPU's bytes; desc-guard ...; fence-strict:
K Queue::Wait calls found the Signal asked for but not yet committed;
cbv-snapshot ...`.

* `fence-strict = 1`: Queue::Wait's early return requires the signalling batch
  to be COMMITTED (`fence->committed`); otherwise it waits for the commit (the
  first 8 logged: `[fence-strict] Queue::Wait for V: the Signal was asked for
  but its batch was not committed yet; waited N ms for the commit`). Every new
  batch command buffer and the present's command buffer start with
  `encodeWaitForEvent(gpu_event, newest committed serial)`, so batches finish
  in serial order on the GPU. A batch that fails on the GPU has its serial
  signalled from the CPU (else every later batch would wait for it forever).
* `fence-strict = 2`: also Signal is synchronous and waits until the GPU has
  finished everything committed so far (all queues) before the fence advances,
  and Present waits for the frame it presents. CPU and GPU no longer overlap;
  FPS drops; diagnosis only.
* `upload-guard = 1`: at replay the UPLOAD/CUSTOM-heap ranges each draw or
  dispatch reads are hashed and kept (with a reference on the resource): a
  root CBV's first 256 bytes and a direct indexed draw's indices exactly; root
  SRVs and vertex buffers as a window of `upload-guard-bytes` (default 256,
  16..4096) from their start. Once the GPU has passed the batch -- before the
  fence the game waits on advances (fence worker, synchronous Signal) and
  before Present returns -- they are hashed again: `[upload-guard] CHANGED while
  the GPU used it: root CBV 1 of 'ps_...' (list#N) -> r#R (UPLOAD heap, 32768
  KB, ml1154 storage) +offset, 256 bytes; batch serial S, GPU at G` (48 lines).
  A window that may reach data the game places after it later is tagged
  "(approximate window: may be data placed after it)" and counted apart.
* `upload-guard = 2`: also, at each batch's commit, one blit copies every noted
  range into a shared buffer (what the GPU sees there at the end of the
  batch); a copy that differs from CPU bytes that never changed is
  `[upload-guard] GPU SAW DIFFERENT BYTES than the CPU wrote: ... first
  difference at +N; batch serial S`.
* `desc-guard = 1`: every shader-visible descriptor heap is watched
  (`[desc-guard] watching shader-visible heap type T, N descriptors`); each
  draw/dispatch stamps the descriptors of its tables (bounded ranges, at most
  256 per table; bindless ranges are not tracked) with its batch; a
  CreateShaderResourceView / CreateConstantBufferView /
  CreateUnorderedAccessView / CreateSampler / CopyDescriptors(Simple) into a
  stamped descriptor whose batch has not finished logs `[desc-guard]
  CopyDescriptorsSimple rewrote descriptor 1234 of the shader-visible heap
  (type 0) while the batch that uses it runs (serial S, GPU at G)` (48 lines).
* `cbv-snapshot = N` (1 = 4096, else 256..16384): every root CBV that points
  into UPLOAD/CUSTOM memory is copied (N bytes, or what is left of the buffer)
  into the list's argument ring at replay, 256-aligned and in the same ring
  chunk as the draw's argument table, and the copy is bound instead. The GPU
  then reads what the game had written at ExecuteCommandLists. A fix attempt
  for root constant buffers only; a cbuffer larger than N reads ring bytes
  past the copy; costs ring memory (N per CBV per draw, reused within a list).

Host test `tests/host/check-got-diagnostics.py` (PASS): static checks that
every hook is behind `g_sd_state`, that the checks run before the fence
advances / Present returns, that Queue::Wait's fast path is unchanged with the
key unset; then the whole block is compiled on the host with stubs and run:
option clamps, batch tickets, CHANGED / approximate / GPU-copy differences,
descriptor writes into an unfinished batch, root-CBV copies (alignment, chunk,
reuse, buffer tail), the strict GPU wait. Clean under ASan/UBSan. The runtime
builds and links for arm64ec (new imports `MTLCommandBuffer_encodeWaitForEvent`
and `MTLSharedEvent_signalValue`, both exported by winemetal). The config
catalog is regenerated, so this ships in an IPA (the catalog is part of the
native ABI), not in a pack.

### 8.6 Device plan

Every block is **one launch**, written into the game's file (Ghost of
Tsushima -> game settings -> "Advanced: this game's config"). Keep
`dxil-tess = 0` in every block. Play 30-60 s at the burning bridge where the
shapes appear, take a screen recording (HUD visible), quit, send log +
recording, then delete the block's other lines.

**Blok G1 -- 303/306, yeni build gerekmez (ilk ve en önemli test):**
```
dxil-tess = 0
upload-swap = 0
```
Log: `ml1154 upload-swap = 0 (Metal-owned storage)`, later `ml1154
CPU-visible buffers on file-backed storage: 0, 0 MB`. Bellek ~100 MB artar
(anonim); oyun bellekten kapanırsa söyle. Ekran: şekiller **tamamen
gittiyse** neden 1 (takas belleğindeki upload tamponları) -> düzeltme: upload
tamponlarını takas katmanının dışında tutmak.

**Blok G2 -- 303/306, yeni build gerekmez:**
```
dxil-tess = 0
ind-probe = 0
```
Log: hiç `[probe]` satırı yok. Ekran: şekiller gittiyse neden 3 (sonda).

**Blok H -- yeni IPA (bu değişiklikler), tek oturumda 1 mi 2 mi:**
```
dxil-tess = 0
upload-guard = 2
upload-guard-bytes = 4096
```
Log: `[sync-diag] madeira-bcd DIAGNOSTIC: fence-strict=0 upload-guard=2 (4096
bytes a range) ...`, then every 300 presents `[sync-diag] present #N: ...`.
Reading:
* `[upload-guard] CHANGED while the GPU used it: root CBV ...` (without
  "approximate") -> cause 2: the game rewrote live data, so it was told too
  early -> Blok I, J.
* `[upload-guard] GPU SAW DIFFERENT BYTES than the CPU wrote ... ml1154
  storage` -> cause 1, even without G1.
* neither while shapes are on screen -> not root CBV / index data: G1, G2, K.
FPS drops a little (hashing).

**Blok I -- yeni IPA:**
```
dxil-tess = 0
fence-strict = 1
```
Log: `[fence-strict] Queue::Wait for ...` lines (each one is cause 2's window
actually happening) and `fence-strict: K` in `[sync-diag]`. Ekran: şekiller
gittiyse sıralama düzeltmesi bu.

**Blok J -- yeni IPA, ağır (FPS düşer):**
```
dxil-tess = 0
fence-strict = 2
```
Ekran: şekiller **bu modda da** varsa CPU/GPU yarışı değil (neden 2 elenir);
yoksa neden 1 veya 2 -- H ayırt eder.

**Blok K -- yeni IPA:**
```
dxil-tess = 0
desc-guard = 1
```
Log: `[desc-guard] watching shader-visible heap type 0, 999000 descriptors`,
then any `[desc-guard] ... rewrote descriptor ...` lines (cause 4).

**Blok L -- yeni IPA, yalnız H root CBV için CHANGED gösterirse:**
```
dxil-tess = 0
cbv-snapshot = 1
```
Log: `cbv-snapshot N copies (M MB)` in `[sync-diag]`. Ekran: şekiller
gittiyse geçici düzeltme bu; kalıcısı, çitin neden erken bittiğini bulmak.

Order: G1 and G2 first (now, no build), then H. G1 plus H decide; I, J, K, L
only as H points.

### 8.7 Paragraph for HANDOFF (ready to paste)

* **GoT one-frame "shapes in the air" after `dxil-tess = 0` (agent,
  2026-10-01; docs/got-corruption.md section 8).** Build 303, log
  `GhostOfTsushima.exe-2026-10-01_21-30-15`, video
  `ScreenRecording_10-01-2026_21-33-21`: `dxil-tess = 0` removed the smoke
  squares (confirms the lit-smoke DXIL tessellation pass). The remaining
  artefact, frame by frame: at least 12 broken frames in 5.2 s of play (one
  game frame in ~6-8), each ONE frame, three kinds -- a dark boulder drawn at
  a wrong place/scale (in front of the cart, on the ground, once floating in
  the sky: 1.37/2.80/3.93/4.67/4.92 s), motion-blur streaks of the bridge
  planks or a tree (1.32/1.97/2.78/3.53/3.98/4.87 s), once blue moonlit
  lighting (0.92 s); no frame-time spike correlation. Reading: right meshes
  with another object's / another frame's per-object data (CPU-written UPLOAD
  data: per-draw constants, the GPU-driven passes' instance stream). Log: all
  8 large UPLOAD/READBACK buffers (82 MB) are on ml1154 storage, which with
  the owner's `swap-mb = 3072` is the file-backed swap tier (file 3069/3072
  MB, footprint 6.5 GB, 1.3 GB compressed); Queue::Wait never slept; 0 GPU
  errors, full fence chain; skips are only the smoke placeholder;
  render-target aliasing and count-buffer records ruled out. Side findings:
  r#739 (256x256 BC3, Metal size 96 KB) placed in a 64 KB slot overlaps r#325
  by 32 KB (texture content); occlusion results never reach GoT's GPU-only
  resolve buffer. Ranked: (1) the GPU reads stale UPLOAD pages on the swap
  tier, (2) premature reuse through an early fence -- one real window:
  queue_Signal sets `submitted` before its batch is committed and the
  synchronous Queue::Wait returns on it, (3) our indirect probe's render-pass
  splits, (4) descriptors rewritten in flight. **Added, all OFF by default,
  D3D12 runtime only:** `fence-strict` (1: Wait needs the commit, every
  batch/present command buffer GPU-waits for the newest committed serial; 2:
  also a synchronous draining Signal and Present waits for its frame),
  `upload-guard` (1: re-hash the UPLOAD ranges draws read once the GPU is
  done, before the fence/Present, `[upload-guard] CHANGED`; 2: also a GPU blit
  copy per batch, `GPU SAW DIFFERENT BYTES`; `upload-guard-bytes`),
  `desc-guard` (`[desc-guard] ... rewrote descriptor ...`), `cbv-snapshot`
  (UPLOAD root CBVs copied into the argument ring at replay). Summary
  `[sync-diag] present #N` every 300 presents. Catalog regenerated (ships in
  an IPA); `tests/host/check-got-diagnostics.py` PASS (ASan/UBSan clean);
  arm64ec build links. **Device plan:** now on 303/306: `upload-swap = 0`,
  then `ind-probe = 0` (each with `dxil-tess = 0`, one launch each); after
  the next IPA: `upload-guard = 2` + `upload-guard-bytes = 4096`, then as it
  points `fence-strict = 1`, `fence-strict = 2`, `desc-guard = 1`,
  `cbv-snapshot = 1`. Open: the fix depends on G1 / H.

## 9. Round 2: G1 / G2 / H on build 313 (2026-10-02 08:42-08:49)

### 9.0 Özet (sahibi için, Türkçe)

* G1 (`upload-swap = 0`), G2 (`ind-probe = 0`) ve H (`upload-guard = 2`)
  şekilleri kaldırmadı. Bu üç şeyi eledi: **takas belleğinde bayat sayfa**
  (GPU'nun kopyası CPU'nunkiyle hep aynı: 18.424 aralıkta 0 fark),
  **oyunun kök (root) sabitlerini erken yazması** (0 değişiklik) ve
  **dolaylı-argüman sondası** (G2).
* Ama H'nin baktığı yer dardı: karede yalnız ~10 aralık. Ghost of Tsushima
  nesne verisini kök sabitlerle değil, **tanımlayıcı (descriptor)
  tabloları** ve **GPU bellekteki tamponlar** ile veriyor; büyük örnek
  (instance) akışları da upload belleğinde değil (yoksa sayı yüzlerce
  olurdu): ya GPU'nun hesapladığı (eleme/culling) ya da kopya kuyruğuyla
  yüklenen veri. Bu yüzden yeni build şunları da izliyor:
  - `upload-guard` artık **tanımlayıcı tablolarının kendisini** (GPU
    kullanırken değişti mi), tablolardaki CBV / tampon SRV'lerin işaret
    ettiği upload verisini ve **CopyBufferRegion / CopyTextureRegion
    kaynaklarını** da izliyor;
  - `queue-trace = 1`: hangi iş parçacığı hangi kuyruğa ne zaman iş veriyor,
    Signal/Wait anında çit (fence) ne durumda (oyun her karede ikinci ve
    üçüncü bir kuyruk kullanıyor: async compute / kopya);
  - `typed-uav-atomic = 1` (deneme düzeltmesi): GPU'da sayaçlı ekleme
    (append) yapan gölgelendiricilerin sayaçları Metal'de "atomik" işaretsiz
    oluşturuluyordu; açıkken işaretli. Eleme sonucu yanlış yuvaya yazılırsa
    tam olarak "başka objenin konumuyla çizilen kaya" görülür.
* **Plan: en fazla 3 açılış, her birinde ekran kaydı (30-60 sn, köprü).**
  Hepsinde `dxil-tess = 0` kalsın. Bölüm 9.4.

### 9.1 What the logs say

| log | block | result |
|---|---|---|
| `f9d252ec-...08-42-13` | G1 `upload-swap = 0` | `ml1154 upload-swap = 0 (Metal-owned storage)`; shapes stay |
| `270ede4f-...08-45-48` | G2 `ind-probe = 0` | no `[probe]`; shapes stay |
| `90453afc-...08-47-52`, `7c4a9de0-...08-48-49` | H `upload-guard = 2`, 4096 bytes | `[sync-diag] present #1800: 18424 ranges noted, 18414 checked, 0 CHANGED (+100 approximate), 18424 copied by the GPU, 0 DIFFERENT` |

All runs: `fence-chain = 1`, `async-submit = 0`, `barrier-render = 0`,
~110-190 encoders a frame, every one waiting on and updating the device fence
(`ml1116 encoders per frame: fence waits N, fence updates N`).

* The 100 "approximate" hits are all `vertex buffer 0 of 'vs_VertexStream'
  -> r#15 (UPLOAD heap, 1024 KB) +168832 / +169216 / +177920 / +178304`:
  windows 384 bytes apart in an immediate-mode vertex ring (UI / debug
  geometry), so the 4096-byte window simply reaches the next draw's vertices.
  Not a race.
* **Coverage:** exactly ~10 noted ranges per frame. H noted root CBV/SRV,
  vertex and index buffers in UPLOAD memory. So the 3D passes bind no
  CPU-written data that way: per-draw constants come through descriptor
  tables, and the GPU-driven passes' streams (the 16 MB instance stream "vb 1",
  stride 8, section 3) are DEFAULT-heap buffers -- written by the GPU (culling
  compute) or by copies (CopyBufferRegion, possibly on the COPY queue). None
  of that was watched.
* Queues: three are busy every frame (batch counters in the log: the DIRECT
  queue, one with 1 list per batch, one with 2 lists per batch; per frame
  `ExecuteCommandLists 9, Signal 8`); `Queue::Wait sleeps 0.0` -- either
  there is no cross-queue Wait, or every one took the early return
  (`queue-trace` answers which).

### 9.2 Ranked causes (round 2)

Ruled out: stale swap-tier pages (G1 and the GPU copy compare), the game
rewriting root CBVs / root SRVs / index data in flight, the probe splits (G2),
render-target aliasing, count buffers (section 8).

1. **GPU-produced per-instance data that is wrong for a frame.** The rock /
   streak shapes are another instance's transform (and previous transform).
   GoT builds its instance lists on the GPU. Candidates inside our runtime:
   a. **append counters / RWBuffer<uint> atomics on Metal texture buffers
      without ShaderAtomic usage** (`typed-uav-atomic`): lost or duplicated
      slots hand a draw another object's data; contention-dependent, so it
      varies frame to frame;
   b. **cross-queue ordering**: culling on the async COMPUTE queue (or the
      instance upload on the COPY queue) and the DIRECT queue's Wait taking
      the early return while the signalling batch is not yet committed
      (section 8.4, cause 2; `fence-strict = 1` closes it and counts it,
      `queue-trace` shows the threads);
   c. **barriers inside an open render pass** are not honoured
      (`barrier-render = 0`: a pass is not closed at a ResourceBarrier, Metal
      orders nothing inside one encoder); `barrier-render = 1` closes it.
2. **Descriptor tables rewritten while the GPU uses them** (`desc-guard`, and
   now `upload-guard`'s table hash) -- desc-guard was never run (0 writes
   checked: it was off).
3. **Upload copies whose source changes before the copy runs** (now watched:
   `copy source` lines).
4. A converter bug in a culling / compaction compute shader (wave ops,
   group-shared memory). Would not react to any switch here; the next step
   would be `capture-cs` on the culling kernels.

### 9.3 What changed (code)

`madeira_d3d12.c`, all OFF unless set:

* `upload-guard` (1 or 2) now also covers, at replay:
  - every **descriptor table** a draw or dispatch binds: the table's own
    descriptors (bounded ranges, up to 256) -> `[upload-guard] DESCRIPTORS
    CHANGED while the GPU used them: descriptor table P of '<shader>' ->
    descriptors A..B of the shader-visible heap`;
  - each **CBV and buffer-SRV descriptor** in those tables that points into
    UPLOAD/CUSTOM memory, over the view's own size (exact; CBVs their first
    256 bytes) -> `table CBV` / `table SRV` in the CHANGED line;
  - the **source of CopyBufferRegion** (exact, up to `upload-guard-bytes`)
    and the first bytes of a buffer->texture copy (approximate) ->
    `copy source`.
  The `[sync-diag]` line adds `N descriptor tables watched, M CHANGED`.
* `queue-trace = N` (1 = 400 lines): `[queue-trace] #k tid T queue Q (type
  0/2/3) Signal|Wait fence F value V: fence at X, asked A, committed C; GPU
  serial S of Z committed` and `... ExecuteCommandLists n list(s)`.
* `typed-uav-atomic = 1`: R32_UINT / R32_SINT UAV texture-buffer views (the
  views behind RWBuffer<uint> and the UAV counters of append/consume buffers)
  are created with MTLTextureUsageShaderAtomic; if Metal refuses, the view is
  created as before (`typed-uav-atomic: Metal refused ...`). Log once:
  `madeira-bcd typed-uav-atomic = 1: ...`.
* Existing and relevant: `barrier-render = 1` (render passes close at every
  ResourceBarrier; each new encoder waits on the device fence),
  `fence-strict = 1 / 2`, `desc-guard = 1`.

Host test `tests/host/check-got-diagnostics.py` (PASS, ASan/UBSan clean):
static checks for the new hooks (all behind `g_sd_state` / the key) and the
harness runs table coverage (descriptor + table CBV/SRV records, a rewritten
descriptor and constant both reported, UAV and GPU-only ranges skipped, one
record per table per replay), copy sources, and queue-trace's line limit.
Catalog regenerated (`queue-trace`, `typed-uav-atomic`): ships in an IPA.

### 9.4 Device plan (next IPA)

One launch per block, `dxil-tess = 0` in all, 30-60 s at the burning bridge,
**screen recording every time** (HUD visible), send log + recording, then
delete the block's other lines.

**Blok K1 -- tanı (dedektörler + hafif sıralama):**
```
dxil-tess = 0
upload-guard = 1
upload-guard-bytes = 1024
desc-guard = 1
queue-trace = 1
fence-strict = 1
```
Log: `[sync-diag] madeira-bcd DIAGNOSTIC: fence-strict=1 upload-guard=1 (1024
bytes a range) desc-guard=1 cbv-snapshot=0 bytes queue-trace=400`,
`[desc-guard] watching shader-visible heap ...`, 400 `[queue-trace]` lines,
then every 300 presents `[sync-diag] present #N: ...`. Read:
* `DESCRIPTORS CHANGED` / `[desc-guard] ... rewrote descriptor` -> cause 2;
* `CHANGED ... table CBV|table SRV|copy source` (not approximate) -> the game
  rewrites data the GPU still needs;
* `[fence-strict] Queue::Wait for ...` lines -> cause 1b happened (and was
  closed in this run: if the shapes are GONE in the recording, that was it);
* `[queue-trace]`: which queue types signal / wait, from which threads.
FPS drops somewhat (hashing).

**Blok K2 -- en güçlü düzeltme denemesi (yavaş):**
```
dxil-tess = 0
typed-uav-atomic = 1
barrier-render = 1
fence-strict = 2
```
Log: `madeira-bcd typed-uav-atomic = 1 ...`, `ml1098 barrier-render = 1`,
`fence-strict=2`. Screen: are the shapes gone? FPS will be low (no CPU/GPU
overlap, more render passes).
* Gone -> Blok K3 decides which of the three.
* Still there -> it is not ordering or atomics: data produced wrongly
  (converter) or a descriptor problem -> K1's lines decide; next step
  `capture-cs` on the culling kernels.

**Blok K3 -- yalnız K2 şekilleri kaldırırsa:**
```
dxil-tess = 0
typed-uav-atomic = 1
```
Gone -> the append-counter atomics (fix: make it the default after a GoW /
GTA check). Still there -> next launch `barrier-render = 1` alone, then
`fence-strict = 1` alone.

### 9.5 Paragraph for HANDOFF (ready to paste)

* **GoT shapes, round 2 (agent, 2026-10-02; docs/got-corruption.md
  section 9).** Build 313: G1 `upload-swap = 0`, G2 `ind-probe = 0`, H
  `upload-guard = 2` (4096 bytes) did not remove the shapes; H: 18424 ranges,
  0 CHANGED, 0 GPU-different (the 100 approximate hits are an immediate-mode
  VB ring, `vs_VertexStream` r#15, windows 384 bytes apart). Rules out stale
  swap-tier pages, root-CBV/SRV/IB rewrites and the probe splits. But H saw
  only ~10 ranges a frame: GoT's 3D passes bind per-draw data through
  descriptor tables and their instance streams are DEFAULT buffers (GPU
  culling or copies), none of which H watched. Re-ranked: (1) GPU-produced
  instance data wrong for a frame -- append-counter / RWBuffer<uint> atomics
  on Metal texture buffers without ShaderAtomic usage, cross-queue (async
  compute / copy) Wait taking the early return before the signal's commit,
  barriers inside an open render pass (`barrier-render = 0`); (2) descriptor
  tables rewritten in flight (desc-guard was never on); (3) upload copy
  sources rewritten before the copy; (4) a converter bug in a culling kernel.
  **Added, OFF by default:** `upload-guard` now also hashes every bound
  descriptor table (`DESCRIPTORS CHANGED`), its CBV / buffer-SRV ranges in
  UPLOAD memory (`table CBV|SRV`) and CopyBufferRegion / CopyTextureRegion
  sources (`copy source`); `queue-trace = N` (thread, queue type, fence
  state per ECL/Signal/Wait); `typed-uav-atomic = 1` (ShaderAtomic usage on
  R32 UAV texture-buffer views, fallback if refused). Host tests PASS (ASan
  clean), arm64ec links, catalog regenerated (IPA). **Device plan** (each
  with `dxil-tess = 0` and a screen recording): K1 `upload-guard = 1`,
  `upload-guard-bytes = 1024`, `desc-guard = 1`, `queue-trace = 1`,
  `fence-strict = 1`; K2 `typed-uav-atomic = 1`, `barrier-render = 1`,
  `fence-strict = 2`; K3 (only if K2 clears them) `typed-uav-atomic = 1`
  alone.
