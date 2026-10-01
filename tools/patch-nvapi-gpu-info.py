#!/usr/bin/env python3
"""GPU memory and core count for NVAPI callers (GTA V Enhanced).

With "Report an NVIDIA GPU" on and the source-built dxgi.dll (IDXGIFactory7),
GTA V Enhanced creates its D3D12 device on the real adapter, then asks NVAPI
for the GPU: GetFullName, GetGpuCoreCount (-104 NOT_SUPPORTED),
GetAllClockFrequencies (-104), and GetPhysicalFrameBufferSize /
GetVirtualFrameBufferSize, which DXMT's nvapi_QueryInterface does not know
("err: nvapi: function ... not implemented"). Right after those it destroys
the device and shows ERR_GFX_D3D_NOD3D12 "Failed to initialize DirectX 12
adapter" (build 303, log PlayGTAV.exe 2026-10-01 21:27:54).

Adds both frame-buffer queries (KB; the Metal device's
recommendedMaxWorkingSetSize, the same number DXGI reports as
DedicatedVideoMemory and as the QueryVideoMemoryInfo budget) and answers
GetGpuCoreCount with the core count of the GPU this NVAPI already names
(GetFullName "NVIDIA GeForce RTX 4090", GetArchInfo AD102: 16384). Ghost of
Tsushima calls none of the three (its logs have no such query). Each logs
its answer through DXMT's Logger (a few calls per launch).

Applied by tools/build-dxmt-nvapi.sh after patch-dxmt-nvapi.py and
patch-nvapi-strings.py, before patch-nvapi-trace.py (which wraps the core
count with its status line). The dxmt submodule is not modified.
Usage: patch-nvapi-gpu-info.py <copy of nvapi.cpp>
"""
import sys

path = sys.argv[1]
src = open(path).read()
marker = "madeira-bcd: GPU memory and core count"
if marker in src:
    print("already patched")
    sys.exit(0)
if "madeira-bcd: NVAPI entry points" not in src:
    sys.exit("patch-nvapi-gpu-info: run patch-dxmt-nvapi.py first")

funcs = r'''
/* madeira-bcd: GPU memory and core count (tools/patch-nvapi-gpu-info.py). */
static uint64_t madeira_gpu_memory_bytes(NvPhysicalGpuHandle hPhysicalGpu) {
  auto devices = WMT::CopyAllDevices();
  for (unsigned i = 0; i < devices.count(); i++) {
    auto device = devices.object(i);
    if (device.registryID() == uint64_t(hPhysicalGpu))
      return device.recommendedMaxWorkingSetSize();
  }
  return 0;
}

NVAPI_INTERFACE
NvAPI_GPU_GetPhysicalFrameBufferSize(NvPhysicalGpuHandle hPhysicalGpu, NvU32 *pSize) {
  if (!hPhysicalGpu || !pSize)
    return NVAPI_INVALID_ARGUMENT;
  uint64_t bytes = madeira_gpu_memory_bytes(hPhysicalGpu);
  if (!bytes)
    return NVAPI_EXPECTED_PHYSICAL_GPU_HANDLE;
  *pSize = NvU32(bytes / 1024);
  Logger::info(str::format("[nvapi] NvAPI_GPU_GetPhysicalFrameBufferSize -> 0 ", *pSize, " KB"));
  return NVAPI_OK;
}

NVAPI_INTERFACE
NvAPI_GPU_GetVirtualFrameBufferSize(NvPhysicalGpuHandle hPhysicalGpu, NvU32 *pSize) {
  if (!hPhysicalGpu || !pSize)
    return NVAPI_INVALID_ARGUMENT;
  uint64_t bytes = madeira_gpu_memory_bytes(hPhysicalGpu);
  if (!bytes)
    return NVAPI_EXPECTED_PHYSICAL_GPU_HANDLE;
  /* Unified memory: nothing beyond the working set is addressable as video memory. */
  *pSize = NvU32(bytes / 1024);
  Logger::info(str::format("[nvapi] NvAPI_GPU_GetVirtualFrameBufferSize -> 0 ", *pSize, " KB"));
  return NVAPI_OK;
}
'''

anchor = 'extern "C" __cdecl void *nvapi_QueryInterface(NvU32 id) {'
if src.count(anchor) != 1:
    sys.exit("patch-nvapi-gpu-info: nvapi_QueryInterface anchor not found")
src = src.replace(anchor, funcs + anchor)

core_old = '''NvAPI_GPU_GetGpuCoreCount(NvPhysicalGpuHandle hPhysicalGpu, NvU32 *pCount) {
  if (!hPhysicalGpu || !pCount)
    return NVAPI_INVALID_ARGUMENT;

  return NVAPI_NOT_SUPPORTED;
}'''
core_new = '''NvAPI_GPU_GetGpuCoreCount(NvPhysicalGpuHandle hPhysicalGpu, NvU32 *pCount) {
  if (!hPhysicalGpu || !pCount)
    return NVAPI_INVALID_ARGUMENT;

  /* madeira-bcd: the GPU GetFullName / GetArchInfo name (RTX 4090, AD102). */
  *pCount = 16384;
  return NVAPI_OK;
}'''
if src.count(core_old) != 1:
    sys.exit("patch-nvapi-gpu-info: NvAPI_GPU_GetGpuCoreCount body not found")
src = src.replace(core_old, core_new)

case_anchor = "  case 0xceee8e9f:\n    return (void *)&NvAPI_GPU_GetFullName;\n"
if src.count(case_anchor) != 1:
    sys.exit("patch-nvapi-gpu-info: QueryInterface table anchor not found")
src = src.replace(case_anchor, case_anchor + """  case 0x46fbeb03:
    return (void *)&NvAPI_GPU_GetPhysicalFrameBufferSize;
  case 0x5a04b644:
    return (void *)&NvAPI_GPU_GetVirtualFrameBufferSize;
""")

open(path, "w").write(src)
print("patch-nvapi-gpu-info: frame-buffer sizes and core count in %s" % path)
