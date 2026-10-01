# GTA V Enhanced: ERR_GFX_D3D_NOD3D12 and the D3D12 capability survey, 2026-10-01

## Özet (sahibi için, Türkçe)

* GTA V Enhanced artık DXGI'yi ve NVAPI'yi geçiyor, cihazı gerçek adaptörde
  oluşturuyor, bir **özellik anketi** yapıyor ve "DirectX 12 (feature level
  12_0) desteklenmiyor" kutusunu gösteriyor. Ankette biz 12_0 iddia
  ediyoruz ama iki cevabımız 12_0 ile çelişiyor: **TiledResourcesTier = 0**
  (Windows'ta 12_0 en az Tier 2 ister) ve **adres bitleri / kaynak = 0**
  (başka bir soruya 40 diyoruz). Ayrıca R32G32B32 biçimlerinin desteği
  sorulduğunda hata dönüyoruz; her 11_0+ ekran kartı bunları köşe (vertex)
  biçimi olarak destekler. `d3d12-typed-uav-load = 1` tek başına yetmedi.
* **Yeni anahtar (varsayılan KAPALI):** `d3d12-tiled-resources = 1`. Açıkken:
  Tier 2 ve 40 adres biti bildiriyoruz, R32G32B32 biçimlerini köşe biçimi
  olarak destekliyoruz, oyun "reserved" (seyrek) kaynak isterse onu
  **tamamen bellekli** oluşturuyoruz (her döşeme gerçek bellekte; tek kaynak
  en fazla 1 GB, `d3d12-reserved-max-mb` ile değişir), döşeme eşleme
  çağrıları sayılıp atlanıyor. Kapalıyken hiçbir şey değişmiyor (God of War
  ve Ghost of Tsushima etkilenmez).
* **Test (yeni IPA gerekir, katalog değişti):** GTA'nın oyun dosyasına
  aşağıdaki satırlar (bölüm 5). Kutu yine çıkarsa logu gönder: hangi
  sorudan sonra cihazı kapattığına bakıp sıradaki cevaba geçeceğiz.

## 1. Evidence

| file | what it shows |
|---|---|
| `af98e0ea-PlayGTAV.exe-2026-10-01_22-23-48.txt` | build 308; probe device (FEATURE_LEVELS only); survey device l.5398-5447; real device l.7399-7435 reads ARCHITECTURE and OPTIONS5 only, then `destroyed Device` and the box |
| `09ff92d3-PlayGTAV.exe-2026-10-01_22-27-37.txt` | the same with `d3d12-typed-uav-load = 1` (`ml1970 typed-uav-load-additional=1 (opt-in)`, l.5341; OPTIONS byte 24 = 01, l.5342); same box (`ERR_GFX_D3D_NOD3D12`, l.7517) |

The survey device asks, in order (feature ids of `[d3d12-caps]`):
FEATURE_LEVELS (12 levels asked, 12_0 answered), OPTIONS, GPU_VIRTUAL_ADDRESS
(40/40), ARCHITECTURE, ARCHITECTURE1, SHADER_MODEL (6.0 asked, 6.0 kept),
OPTIONS1 (wave 32, int64), ROOT_SIGNATURE (1.1), OPTIONS2 (0), OPTIONS5
(0), SHADER_CACHE, then a FORMAT_SUPPORT pass over the DXGI formats: the
ones we fail are logged as `texture format N has no Metal mapping` -- 5-8
(R32G32B32_TYPELESS/FLOAT/UINT/SINT), 66 (R1), 68/69 (R8G8_B8G8,
G8R8_G8B8), 89 (R10G10B10_XR_BIAS_A2), 100-115 (video formats, B4G4R4A4) and
130-132 -- then `destroyed Device`.

The OPTIONS answer (60 bytes) decoded:

| offset | field | answer | FL 12_0 on Windows |
|---|---|---|---|
| 12 | TiledResourcesTier | **0** | **Tier 2 required** |
| 16 | ResourceBindingTier | 2 | Tier 2 required |
| 24 | TypedUAVLoadAdditionalFormats | 0 (1 with ml1970) | required |
| 28 / 32 | ROVsSupported / ConservativeRasterizationTier | 0 / 0 | 12_1 only |
| 36 | MaxGPUVirtualAddressBitsPerResource | **0** | real GPUs 40-44; our GPU_VIRTUAL_ADDRESS_SUPPORT says 40 |
| 56 | ResourceHeapTier | 2 | -- |

With typed UAV loads already on, the remaining contradictions are
TiledResourcesTier, the per-resource address bits, and failed format
queries for formats every 11_0+ device supports at least as vertex formats
(R32G32B32_FLOAT/UINT/SINT; our input layouts take them: float3 / uint3 /
int3). Winlator (vkd3d-proton on Turnip), which runs the game, reports
tiled resources tier 2/3 and supports R32G32B32.

## 2. What changed (code)

`madeira-d3d12/src/pe/madeira_d3d12.c`, block "TILED RESOURCES (opt-in)"
after `device_CreateCommittedResource3`, keys read once by `mad_tiled_on`:

* `d3d12-tiled-resources = 1` (default 0). One line when on:
  `[d3d12-caps] madeira-bcd tiled-resources=1 (opt-in): TiledResourcesTier 2,
  MaxGPUVirtualAddressBitsPerResource 40, R32G32B32 vertex formats; reserved
  resources fully backed, at most 1024 MB each; tile mappings are no-ops`.
  * CheckFeatureSupport(OPTIONS): `TiledResourcesTier = TIER_2`,
    `MaxGPUVirtualAddressBitsPerResource = 40`.
  * CheckFeatureSupport(FORMAT_SUPPORT) for R32G32B32_FLOAT / UINT / SINT:
    `S_OK`, `Support1 = IA_VERTEX_BUFFER` only (Metal has no 96-bit texture or
    texture-buffer format; nothing else is claimed). TYPELESS and the other
    unmapped formats keep failing as before.
  * CreateReservedResource / CreateReservedResource1 / CreateReservedResource2:
    the resource is created exactly as a committed resource in a DEFAULT heap
    (`mad_create_resource`), so every tile is backed by memory of its own.
    The tiling decides the size: tiles x 64 KB above `d3d12-reserved-max-mb`
    (default 1024) is refused with `E_OUTOFMEMORY` before anything is
    allocated; 1D textures and formats without a standard tile shape
    (96-bit, MSAA block-compressed) are refused with `E_INVALIDARG`; a NULL
    out pointer is the documented capability test (`S_FALSE`). Protected
    sessions and castable-format lists are refused as for committed
    resources. Log (64 lines): `[d3d12-tiled] CreateReservedResource r#N:
    dimension D format F WxHxD, M mip(s), S sample(s), flags X -> T tiles of
    w x h x d (n standard + p packed mips, packed in k tile(s) a slice), fully
    backed; L reserved resource(s) live, B MB`; refusals as
    `[d3d12-tiled] ... refused: ...`. The live count and size go down when a
    reserved resource is released.
  * GetResourceTiling: D3D12's standard tiling. 64 KB tiles; 2D shapes
    256x256 / 256x128 / 128x128 / 128x64 / 64x64 for 8/16/32/64/128-bit
    texels, 512x256 for BC1/BC4 and 256x256 for BC2/3/5/6H/7; 3D 64x32x32 /
    32x32x32 / 32x32x16 / 32x16x16 / 16x16x16, BC 128x64x16 / 64x64x16; MSAA
    halves width, then height per doubling of the sample count (Vulkan's
    standard sparse block shapes, which follow D3D's standard swizzle).
    Tier 2 packing: a mip is standard while it fills a whole tile in every
    dimension; the rest are packed per array slice into whole tiles (their
    linear size rounded up, at least one). Tile order: slice 0's standard
    mips, slice 0's packed tail, slice 1, ...; packed subresources report
    `D3D12_PACKED_TILE` and zero size; `PackedMipInfo.StartTileIndex...` is
    slice 0's tail. Buffers: 65536 x 1 x 1, one subresource, no mip info. A
    resource that was not created reserved gets zeros. Log (16 lines):
    `[d3d12-tiled] GetResourceTiling r#N: ...`.
  * ID3D12CommandQueue::UpdateTileMappings / CopyTileMappings: no-ops,
    counted; the first 8 and every 1000th are logged with resource, first
    region (coordinate, tiles, box), heap, first range (flags, heap offset,
    tiles) and flags.
* Without the key every one of these methods is the generated stub it was
  (E_NOTIMPL / no-op, `madeira_d3d12_note_unimplemented`), OPTIONS and
  FORMAT_SUPPORT answer exactly as before, nothing is logged. God of War
  (D3D11 / DXMT) never reaches this file; Ghost of Tsushima does not change
  without the key.

**Deviations from Tier 2, on purpose:** a tile the application never mapped
(or mapped to NULL) is still backed: it reads what was last written there
(initially whatever Metal's fresh allocation holds), not zeros, and writes to
it are kept. Mapping two tiles to the same heap tile does not alias them. A
heap the game creates as a tile pool is allocated too (DEFAULT heaps are
Metal placement heaps, ml1145), so a game that streams through a big tile pool
pays for the pool AND the full backing; watch `ml1057` / `ml1150` memory lines.
Also lenient: 3D reserved textures (Tier 3) are accepted.
ID3D12GraphicsCommandList::CopyTiles is still the stub.

**Later, real residency:** Metal sparse textures (MTLHeapTypeSparse,
64 KB sparse pages, mappings updated on a resource-state encoder) cover
textures; Metal 4's placement sparse resources (iOS 26+) map tiles of a
placement heap into buffers and textures, which is D3D12's heap + tile model
-- UpdateTileMappings would then map instead of being a no-op, and unmapped
tiles could read zeros.

Host test `tests/host/check-d3d12-tiled.py` (PASS): static checks (key
defaults, every method falls back to its stub when off, OPTIONS /
FORMAT_SUPPORT answers behind the key, vtables, cap before allocation, live
total) and the tiling code compiled and run on the host against the tables
above (2D / 3D / BC / MSAA shapes, packing, slices, buffers, refusals).
`tests/host/check-got-diagnostics.py` still PASS. The runtime builds and links
for arm64ec. Config catalog regenerated (`d3d12-tiled-resources`,
`d3d12-reserved-max-mb`), so this ships in an IPA, not a pack.

## 3. Device test

Game file of GTA V Enhanced (game settings -> "Advanced: this game's config"),
one launch:

```
env.MADEIRA_DXGI_SRC = 1
env.MADEIRA_GUEST_LOG = all
vram-mb = 4096
d3d12-typed-uav-load = 1
d3d12-tiled-resources = 1
```

Expected in the log:

* `[d3d12-caps] madeira-bcd tiled-resources=1 (opt-in): ...` before the
  OPTIONS line;
* the OPTIONS answer `CheckFeatureSupport(feature 0, 60 bytes) -> 0x00000000
  000000000000000000000000020000000200000000000000010000000000000000000000280000000000000000000000000000000100000002000000`
  (byte 12 = 02 tiled tier, byte 24 = 01 typed UAV loads, byte 36 = 0x28 = 40);
* `texture format 6/7/8 has no Metal mapping` gone (5 stays);
* if the game goes on: `[d3d12-tiled] CreateReservedResource ...`,
  `GetResourceTiling ...`, `UpdateTileMappings ...` lines.

If the box still comes: send the log. Next candidates, in order: the
remaining FORMAT_SUPPORT failures (B4G4R4A4, R8G8_B8G8 / G8R8_G8B8 are
11_0-era formats; the video formats are optional), ResourceBindingTier 3
(vkd3d-proton reports it), OPTIONS12 (enhanced barriers, the Agility SDK
feature the box names), shader model above 6.6, and the
`NvAPI_GPU_GetAllClockFrequencies -> -104` (NOT_SUPPORTED) answer.

## 4. Paragraph for HANDOFF (ready to paste)

* **GTA V Enhanced: opt-in tiled resources for the FL 12_0 survey (agent,
  2026-10-01; docs/gta5-d3d12-caps.md).** Logs PlayGTAV.exe 22:23:48 /
  22:27:37 (build 308): the survey device's answers contradict the 12_0 we
  claim in OPTIONS.TiledResourcesTier (0; 12_0 requires Tier 2) and
  OPTIONS.MaxGPUVirtualAddressBitsPerResource (0, while
  GPU_VIRTUAL_ADDRESS_SUPPORT says 40), and its FORMAT_SUPPORT pass gets
  E_FAIL for R32G32B32_FLOAT/UINT/SINT (every 11_0+ device has them as vertex
  formats; so do our input layouts) right before `destroyed Device`; typed
  UAV loads alone did not help. **Added, OFF by default (key
  `d3d12-tiled-resources = 1`, madeira.cfg or game file):** OPTIONS
  TiledResourcesTier 2 + 40 VA bits per resource; FORMAT_SUPPORT R32G32B32
  FLOAT/UINT/SINT = IA_VERTEX_BUFFER; CreateReservedResource(1,2) create the
  resource FULLY BACKED like a committed DEFAULT-heap resource, tile count x
  64 KB capped by `d3d12-reserved-max-mb` (default 1024, E_OUTOFMEMORY above,
  checked before allocating), logged with live totals; GetResourceTiling
  answers D3D12's standard tiling (64 KB tiles, standard 2D/3D/BC/MSAA
  shapes, Tier 2 per-slice mip packing, D3D12_PACKED_TILE for packed
  subresources); UpdateTileMappings / CopyTileMappings counted no-ops
  (first 8 logged). Deviation: unmapped tiles read their backing, not zeros;
  tile-pool heaps are allocated besides the full backing. Without the key
  every method is the old stub and every answer unchanged (GoW / GoT
  untouched). Host test `tests/host/check-d3d12-tiled.py` (new) PASS incl. a
  GetResourceTiling table test; got-diagnostics PASS; arm64ec builds and
  links; catalog regenerated (IPA). **Device test** (next IPA): GTA game file
  `env.MADEIRA_DXGI_SRC = 1`, `env.MADEIRA_GUEST_LOG = all`, `vram-mb = 4096`,
  `d3d12-typed-uav-load = 1`, `d3d12-tiled-resources = 1`; expect the
  `tiled-resources=1 (opt-in)` line and OPTIONS bytes 12 = 02, 36 = 28. If
  the box stays: remaining format failures (B4G4R4A4, R8G8_B8G8),
  ResourceBindingTier 3, OPTIONS12, SM > 6.6, NVAPI clock query. Later:
  real residency via Metal sparse textures / Metal 4 placement sparse.
