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

## 5. D3DKMT adapter (2026-10-02, build 314 log)

### Özet (sahibi için, Türkçe)

* Son logda (09:02:54, build 314) oyun cihazı oluşturmadan hemen önce üç kez
  `D3DKMTEnumAdapters2` çağırıyor ve **0 adaptör** alıyor: iOS'taki sanal
  monitör düzeninde Wine'ın GPU listesi boş. Windows'ta DXGI'nin ekran kartı
  burada da (aynı LUID ile) görünür ve sürücü sürümü, WDDM sürümü, donanım
  zamanlaması gibi bilgiler buradan okunur ("sürücünüzü güncelleyin"
  uyarısının klasik kaynağı).
* Üç çağrının her biri bir NVIDIA Streamline eklentisi yüklendikten hemen
  sonra geliyor (sl.common, sl.dlss/nvngx_dlss, sl.dlss_g); oyunun kendi
  cihaz denemesinde ve kutudan sonraki ikinci denemede hiç D3DKMT
  numaralandırması yok. Yani bu büyük olasılıkla Streamline'ın kontrolü,
  GTA'nın kendisi değil. Kesin olmak için artık **her D3DKMT çağrısı
  loglanıyor** (ör. `[vkmt] tid=... QueryAdapterInfo type=70 (WDDM_2_7_CAPS)`).
* **Yeni anahtar (varsayılan KAPALI):** `env.MADEIRA_KMT_ADAPTER = 1`.
  Açıkken ekran kartı D3DKMT'de tek adaptör olarak listeleniyor (DXGI,
  D3D12 ve NVAPI ile aynı LUID), sorulara WDDM 3.1 masaüstü sürücüsü gibi
  cevap veriyor (sürücü 35.0.15.6094, "NVIDIA GeForce RTX 3060", 10de:2544,
  donanım zamanlaması açık, bellek = `vram-mb`); DXGI'nin
  `CheckInterfaceSupport` sürücü sürümü de artık ~0 değil, aynı sürüm
  (dxgi-src.dll ile). Kapalıyken hiçbir cevap değişmiyor (God of War, Ghost
  of Tsushima etkilenmez); yalnız birkaç `[vkmt]` log satırı eklendi.
* **Test (yeni IPA gerekir: win32u ve katalog değişti):** GTA'nın oyun
  dosyası aşağıda (5.4). Kutu yine çıkarsa logu gönder: `[vkmt]` ve
  `[dxgi-src] CheckInterfaceSupport` satırları kimin neyi sorduğunu gösterecek.

### 5.1 Evidence

`3105a993-PlayGTAV.exe-2026-10-02_09-02-54.txt` (build 314; the same pattern
in `dfcc59b8-...08-33-51.txt`, lines 7305 / 7386 / 7425), all on the game's
main thread 0034:

| line | event |
|---|---|
| 5962 | `sl.interposer.dll` loaded (Streamline) |
| 7176, 7186 | `sl.common.dll`, then `d3d12.dll` (madeira_d3d12) loaded |
| 7308-7309 | first display-device touch of the process: `[display] virtual monitor`, `[vgpu] registered ...10DE&DEV_2544... driver 35.0.15.6094` |
| **7310** | `[vkmt] D3DKMTEnumAdapters2 -> 0, 0 adapters` |
| 7311-7330 | DXGI factory (IDXGIFactory, 7b7166ec); NVAPI init, driver/branch, logical GPU |
| 7371-7392 | `sl.dlss.dll`, then **7392** EnumAdapters2 -> 0 adapters, then `nvngx_dlss.dll` mapped |
| 7418-7431 | `sl.dlss_g.dll` (DLSS Frame Generation), then **7431** EnumAdapters2 -> 0 adapters |
| 7446, 7471 | `sl.pcl.dll`, `sl.reflex.dll` |
| 7494-7535 | RegisterAdaptersChangedEvent, the real `D3D12CreateDevice`, NVAPI (display handle, GPUs, name, cores, clocks, frame buffer 4 GB), ARCHITECTURE, OPTIONS5 (DXR 1.1), MSAA x1..x8, `destroyed Device` |
| 7672-7708 | `ERR_GFX_D3D_NOD3D12` box |
| 8186-8248 | int3 at GTA5_Enhanced.exe+0x100798 (its retry path), a second real device: the same NVAPI + caps sequence, `destroyed Device`, **no D3DKMT enumeration** (the old line allowed 4, only 3 were printed) |

So the enumerations line up one-to-one with Streamline plugin loads (each
plugin checks the system when it loads; DLSS Frame Generation needs hardware
GPU scheduling, which Windows reports only through
`D3DKMTQueryAdapterInfo(KMTQAITYPE_WDDM_2_7_CAPS)` on an enumerated adapter),
and GTA's own adapter check -- the part that repeats on retry -- does not
enumerate. With 0 adapters a caller has nothing to query, so the
"conversation" in build 314 ends at the enumeration; whether GTA (or DXGI on
its behalf) opens an adapter by LUID and queries it was invisible, because
build 314 logged only EnumAdapters2. The box text ("ensure your Windows
installation supports DirectX 12 Agility SDK, or update your graphics
driver") is GTA's generic adapter-init failure text, so the D3DKMT gap is a
lead, not a proof.

Upstream Wine (pin 4f5b197) answers, for comparison:

| entry point | upstream |
|---|---|
| EnumAdapters2 / EnumAdapters | the GPUs in `gpus` (Vulkan / OpenGL / display driver); none in the iOS virtual-monitor regime |
| OpenAdapterFromLuid | any LUID, a new handle (Vulkan device by LUID: none here) |
| OpenAdapterFromHdc | stub, STATUS_NO_MEMORY |
| OpenAdapterFromDeviceName | a `gpus` path, else STATUS_INVALID_PARAMETER |
| OpenAdapterFromGdiDisplayName | (ours, ml1006) `\\.\DISPLAY1` -> the first GPU's LUID or a software LUID |
| QueryAdapterInfo | CHECKDRIVERUPDATESTATUS = FALSE, DRIVERVERSION = WDDM **1.3**; everything else STATUS_NOT_IMPLEMENTED |
| QueryVideoMemoryInfo | Vulkan budget; zeros here |
| QueryStatistics | stub, success, nothing filled |
| CheckVidPnExclusiveOwnership | success unless an exclusive owner exists |
| CheckOcclusion | stub, STATUS_PROCEDURE_NOT_FOUND |

(gdi32's `D3DKMT*` exports forward to these win32u syscalls.) DXGI's own
adapter opens a KMT handle from its LUID in its constructor
(`dxgi_adapter.cpp`, `D3DKMTOpenAdapterFromLuid`), and its
`CheckInterfaceSupport` returned UMD version `~0`.

### 5.2 What changed (code)

* `build/win32u-unix/d3dkmt_ios.c` (new; `build.sh` compiles it instead of
  upstream `d3dkmt.c`, which it includes with 13 entry points renamed
  `upstream_*`, the pattern of `syscall_ios.c`):
  * **Trace, always on, bounded** (`[vkmt] tid=XXXX ...`): OpenAdapterFromLuid
    (LUID, handle and, with the key, whether it is the madeira adapter),
    OpenAdapterFromHdc, CloseAdapter, CreateDevice, DestroyDevice,
    QueryAdapterInfo (handle, type number and name, size, status, the first
    8 bytes of small answers, `madeira adapter` / `upstream`),
    QueryVideoMemoryInfo, QueryStatistics (type, LUID), SetQueuedLimit,
    SetVidPnSourceOwner, CheckOcclusion, CheckVidPnExclusiveOwnership, Escape.
    First 16 calls of each, failures up to the 64th; QueryAdapterInfo the
    first 64 calls and the first call of every type after that.
  * **`env.MADEIRA_KMT_ADAPTER = 1`** (also on/true/yes; read once with
    getenv; one line `[vkmt] madeira-bcd kmt-adapter=1 ...`):
    * LUID = bswap64(`MTLCreateSystemDefaultDevice().registryID`), the value
      DXMT's `GetAdapterLuid` (DXGI desc, EnumAdapterByLuid), NVAPI and
      madeira_d3d12's `GetAdapterLuid` use. Resolved with dlsym(RTLD_DEFAULT)
      (`MTLCreateSystemDefaultDevice`, `sel_registerName`, `objc_msgSend`), so
      win32u needs no Objective-C and no link change; computed once
      (`[vkmt] adapter LUID hi:lo (bswap64 of Metal registryID 0x...)`). No
      Metal device -> logged, no adapter.
    * QueryAdapterInfo for any open adapter handle (there is one GPU):
      DRIVERVERSION(_RENDER) = KMT_DRIVERVERSION_WDDM_3_1; UMD_DRIVER_VERSION /
      KMD_DRIVER_VERSION = the registry DriverVersion as Windows encodes it,
      35.0.15.6094 -> 0x00230000000F17CE (NVAPI keeps its own 999.99);
      ADAPTERTYPE(_RENDER) = RenderSupported | DisplaySupported (not
      software); PHYSICALADAPTERCOUNT = 1; PHYSICALADAPTERDEVICEIDS = 10de:2544,
      subsystem / revision 0 (as the registry path), BusType PCI, adapter
      index > 0 invalid; ADAPTERADDRESS(_RENDER) = bus 0 (the registry's bus
      number), device 0, function 0; WDDM_1_2_CAPS = DMA-buffer preemption
      (as DXGI's desc) + NonVGA / SmoothRotation / PerEngineTDR / CCD /
      GammaRamp / HWCursor / HWVSync; WDDM_1_3_CAPS = 0; WDDM_2_0_CAPS =
      64-bit atomics + GPU MMU; **WDDM_2_7_CAPS = HwSchSupported | HwSchEnabled
      | HwSchEnabledByDefault**; WDDM_2_9_CAPS = HwSch support state STABLE +
      enabled; WDDM_3_0 / 3_1 caps = 0; DRIVER_DESCRIPTION(_RENDER) = "NVIDIA
      GeForce RTX 3060"; ADAPTERREGISTRYINFO(_RENDER) = name / name /
      "Integrated RAMDAC" / name (what `write_gpu_to_registry` stores);
      NODEMETADATA node 0 = 3D "3D", node 1 = copy "Copy" (GPU MMU), others
      invalid; GETSEGMENTSIZE = dedicated only, GETSEGMENTGROUPSIZE = legacy +
      local = dedicated, nothing non-local (DXGI's desc says shared 0). A
      buffer smaller than the type's structure gets STATUS_INVALID_PARAMETER.
      Every other type (UMDRIVERNAME -- there is no UMD DLL to name --,
      ADAPTERGUID, CHECKDRIVERUPDATESTATUS, perf data, ...) keeps upstream's
      answer and is logged.
    * Dedicated size = `vram-mb` (madeira.cfg / game file, >= 256) else
      4096 MB: the fixed part of DXGI's budget (winemetal ml1042) and the
      registry's memory size.
    * OpenAdapterFromHdc opens the adapter (VidPnSourceId 1, as the GDI
      display name path); QueryVideoMemoryInfo's LOCAL budget = dedicated,
      AvailableForReservation half of it (upstream leaves 0 without Vulkan).
* `build/win32u-unix/sysparams_ios.c`, all behind the same key:
  * `NtGdiDdDDIEnumAdapters2` (and so EnumAdapters): when `gpus` is empty
    (the virtual-monitor regime), one adapter: a handle opened from the LUID,
    the LUID, NumOfSources 1. The log line now carries the thread id and also
    logs the size query `EnumAdapters2(NULL)` (8 lines).
  * `NtGdiDdDDIOpenAdapterFromDeviceName`: the registry GPU's interface path
    (`\\?\PCI#VEN_10DE&DEV_2544&SUBSYS_00000000&REV_00#00000000#{1CA05180-...}`,
    which SetupAPI lists) opens it; traced (8 lines).
  * OpenAdapterFromGdiDisplayName's virtual adapter (ml1006) uses the LUID.
  * `ios_register_virtual_gpu`: the registry GPU gets the LUID
    (`DEVPROPKEY_GPU_LUID`, `DirectX\{guid}\AdapterLuid`), the dedicated size
    and `DirectX\{guid}\DriverVersion` = the DriverVersion QWORD (was
    0x230000000f1ff4 = 35.0.15.8180, "some version in the future"); log
    `[vgpu] registered ... (MADEIRA_KMT_ADAPTER: ...)`.
  * `madeira_kmt_identity()`: vendor / device / name / DriverVersion / path
    of the registry GPU, for d3dkmt_ios.c (`build/win32u-unix/madeira_kmt.h`).
* `tools/patch-dxgi-umd-version.py` (new; `tools/build-dxgi-dll.sh` applies
  it to a copy of `dxgi_adapter.cpp` for dxgi-src.dll, the plain recipe link
  keeps the pristine file, and the build checks the patch string is in the
  DLL): `CheckInterfaceSupport` asks
  `D3DKMTQueryAdapterInfo(KMTQAITYPE_UMD_DRIVER_VERSION)` on the adapter's
  own KMT handle when `MADEIRA_KMT_ADAPTER=1`, as Windows' DXGI does; without
  the key or on failure `~0` as upstream. Logs the first 4 calls
  (`[dxgi-src] CheckInterfaceSupport <guid> -> S_OK` and `[dxgi-src]
  CheckInterfaceSupport: UMD version 35.0.15.6094 from D3DKMT (...)`).
  The name is outside the i386 farm's `tools/patch-dxmt-*.py` cache key.
* Catalog: `env.MADEIRA_KMT_ADAPTER` (bool, default 0, "Windows, display &
  input"); `vram-mb` keeps its DXMT category and note (overlay), with
  d3dkmt_ios.c added to its sources.

Without the key every answer, the registry and DXGI's `~0` are as before;
only `[vkmt]` lines are added (bounded), and upstream's FIXME/TRACE messages
of the wrapped functions now name `upstream_NtGdiDdDDI...`. God of War
(D3D11) does not enumerate KMT adapters; DXMT's dxgi opens one handle per
adapter.

**Limits:** in remote-Metal mode (winemetal `wmtr`) DXGI's LUID is the host's
registryID and this one the phone's; the trace then says "not the madeira
adapter's LUID". QueryStatistics stays upstream's empty stub (its segment /
node counts are the next thing to fill if the trace shows a caller). The
non-local budget is 0.

### 5.3 Verified

* `tests/host/check-kmt-adapter.py` PASS (79 checks, with `WINE_SRC=` /
  `DXMT_SRC=` pointing at the main checkout's submodules and `MINGW=` at
  llvm-mingw 20260421): wiring of both files; the kmt-test region compiled
  on the host (ASan/UBSan) against the KMTQAITYPE values of the wine pin's
  `d3dkmthk.h` -- every answer, structure size (QUERY_DEVICE_IDS 28,
  ADAPTERADDRESS 12, ADAPTERREGISTRYINFO 2080, DRIVER_DESCRIPTION 8192,
  SEGMENTSIZEINFO 24, SEGMENTGROUPSIZEINFO 56, NODEMETADATA 80, WDDM_1_2_CAPS
  12), short buffers, bad indices, types left to upstream, the version QWORD,
  the LUID against DXMT's formula; the switch, the dlsym Metal lookup (fake
  `MTLCreateSystemDefaultDevice` / `objc_msgSend`: one lookup, device
  released; none -> no adapter) and the dedicated size from madeira.cfg /
  the game file; the DXGI patch (once, gated, `~0` fallback, moved anchor
  refused) compiled for arm64ec.
* `sysparams_ios.c` and `d3dkmt_ios.c` pass `clang -fsyntax-only -Wall`
  (WINE_IOS, host-configured wine headers) with no warning; `d3dkmt_ios.c`
  compiles to an object exporting the 13 wrappers and the `upstream_*`
  functions.
* `tools/build-dxgi-dll.sh` with llvm-mingw 20260421 (Linux host): the patched
  dxgi-src.dll links, its exports equal the committed dxgi.dll's, it imports
  `gdi32.D3DKMTQueryAdapterInfo`; the plain (recipe) link is symbol-identical
  to the one before this change (on this host both match 9236 of 9663
  symbols of the committed binary, a host-toolchain difference that predates
  this change; CI on macOS reproduces it fully).
* `check-dxgi-factory7.py`, `check-vmon-identity.py`,
  `check-got-diagnostics.py`, `check-win32u-zero-bits.py` PASS; the catalog
  is current (generator run against the main checkout's submodules).
* Not verified: an iOS build of win32u (no Xcode here) and the device run.

### 5.4 Device test

Next IPA (win32u is native code; the catalog changed). GTA V Enhanced's game
file, one launch:

```
env.MADEIRA_DXGI_SRC = 1
env.MADEIRA_GUEST_LOG = all
env.MADEIRA_KMT_ADAPTER = 1
vram-mb = 4096
d3d12-typed-uav-load = 1
d3d12-tiled-resources = 1
d3d12-tile-based = 0
d3d12-caps-log = 2
d3d12-msaa8 = 1
d3d12-raytracing-tier = 11
```

Expected in the log:

* `[vkmt] madeira-bcd kmt-adapter=1 (MADEIRA_KMT_ADAPTER): ...` and
  `[vkmt] adapter LUID hi:lo (bswap64 of Metal registryID 0x...)`;
* `[vgpu] registered ... driver 35.0.15.6094 (MADEIRA_KMT_ADAPTER: ...)`;
* `[vkmt] tid=0034 D3DKMTEnumAdapters2 -> 0, 1 adapters (MADEIRA_KMT_ADAPTER:
  the DXGI/D3D12 adapter, luid ..., hAdapter ...)` three times, each followed
  by what the caller asks, e.g. `[vkmt] tid=0034 QueryAdapterInfo
  hAdapter=... type=70 (WDDM_2_7_CAPS) size=4 -> 0 value=0x7 (madeira adapter)`;
* `[vkmt] ... OpenAdapterFromLuid luid=... (the madeira adapter)` from DXGI's
  adapters (the LUID must equal the EnumAdapters2 one);
* `[dxgi-src] CheckInterfaceSupport {...} -> S_OK` and `UMD version
  35.0.15.6094 from D3DKMT` if anything asks.

The same build without `env.MADEIRA_KMT_ADAPTER` shows the whole D3DKMT
conversation with upstream's answers (0 adapters): a useful A/B.

### 5.5 Next candidates if the box stays

1. Whatever the new `[vkmt]` lines show answered by `upstream` with
   STATUS_NOT_IMPLEMENTED (0xc0000002) or an invalid parameter right before
   the real device: answer that type next. QueryStatistics (adapter /
   segment / node counts) is the most likely gap if a caller uses it.
2. Driver version policy: the registry / KMT say 35.0.15.6094 (= NVIDIA
   560.94), NVAPI says 999.99 (branch r57218). If GTA's minimum NVIDIA driver
   is newer than 560.94 (the Enhanced edition shipped in March 2025 with
   57x drivers; not verified), the registry DriverVersion
   (`driver_vendor_to_version` in sysparams_ios.c) should become a 57x one
   (e.g. 32.0.15.7xxx). The identity mismatch NVAPI RTX 4090 vs DXGI /
   registry RTX 3060 is also still open.
3. If no `[dxgi-src] CheckInterfaceSupport` line appears and the trace shows
   no D3DKMT query from GTA's own path, the decision is in data it already
   has (NVAPI answers, the survey's caps): compare with a Windows run's
   NVAPI / CheckFeatureSupport answers.
4. Earlier list: remaining FORMAT_SUPPORT failures (B4G4R4A4, R8G8_B8G8),
   ResourceBindingTier 3, OPTIONS12, shader model above 6.6.

### 5.6 Paragraph for HANDOFF (ready to paste)

* **GTA V Enhanced: opt-in D3DKMT adapter + [vkmt] trace (agent, 2026-10-02;
  docs/gta5-d3d12-caps.md section 5).** Log PlayGTAV.exe 09:02:54 (build
  314; same in 08:33:51): thread 0034 calls `D3DKMTEnumAdapters2` three
  times (l.7310 / 7392 / 7431) and gets 0 adapters (the iOS virtual-monitor
  regime lists no GPU); each call follows a Streamline plugin load
  (sl.common, sl.dlss/nvngx_dlss, sl.dlss_g), and GTA's own device check and
  its retry after the box (l.8228-8248) do not enumerate, so the callers are
  most likely Streamline's (hardware-scheduling check for DLSS-G), not GTA's
  driver check: a lead, not a proof. Build 314 logged nothing else of
  D3DKMT. **Added:** `build/win32u-unix/d3dkmt_ios.c` wraps upstream
  `d3dkmt.c` (13 entry points renamed `upstream_*`): an always-on, bounded
  `[vkmt] tid=` trace of every adapter-level D3DKMT entry point
  (QueryAdapterInfo with type name, first 64 calls + first of each type).
  **OFF by default, `env.MADEIRA_KMT_ADAPTER = 1`:** EnumAdapters2 lists one
  adapter with the DXGI / madeira_d3d12 / NVAPI LUID (bswap64 of the Metal
  registryID, via dlsym), OpenAdapterFromHdc / FromDeviceName /
  FromGdiDisplayName open it, the registry GPU and its DirectX key carry that
  LUID and the DriverVersion QWORD, QueryAdapterInfo answers WDDM 3.1
  (DRIVERVERSION 3100, UMD/KMD version 35.0.15.6094 = 0x00230000000F17CE,
  ADAPTERTYPE render+display, 10de:2544 ids, WDDM 1.2-3.1 caps with HAGS on,
  DRIVER_DESCRIPTION / ADAPTERREGISTRYINFO "NVIDIA GeForce RTX 3060",
  NODEMETADATA, segment sizes = vram-mb or 4096 MB), other types upstream +
  logged; QueryVideoMemoryInfo's LOCAL budget = the same size;
  `tools/patch-dxgi-umd-version.py` (dxgi-src.dll) makes
  CheckInterfaceSupport return that version from D3DKMT instead of ~0. Off:
  answers unchanged (GoW / GoT untouched), only `[vkmt]` lines. Host test
  `tests/host/check-kmt-adapter.py` (new, 79 checks) PASS; -Wall clean;
  dxgi-src.dll links for arm64ec; factory7 / vmon / got-diagnostics /
  zero-bits PASS; catalog regenerated (IPA). **Device test** (next IPA): GTA
  game file `env.MADEIRA_DXGI_SRC = 1`, `env.MADEIRA_GUEST_LOG = all`,
  `env.MADEIRA_KMT_ADAPTER = 1`, `vram-mb = 4096`, `d3d12-typed-uav-load = 1`,
  `d3d12-tiled-resources = 1`, `d3d12-tile-based = 0`, `d3d12-caps-log = 2`,
  `d3d12-msaa8 = 1`, `d3d12-raytracing-tier = 11`; expect
  `EnumAdapters2 -> 0, 1 adapters (MADEIRA_KMT_ADAPTER ...)` and the
  `[vkmt] QueryAdapterInfo` lines after it. If the box stays: the
  upstream-answered types in the trace, QueryStatistics, the driver version
  (560.94 may be under GTA's minimum; NVAPI says 999.99), whether
  CheckInterfaceSupport is called at all, then the earlier caps list.
