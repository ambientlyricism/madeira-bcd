#!/usr/bin/env python3
"""Check opt-in graphics wrappers and the linked ARM64EC entry-point ABI.

Without arguments, exercise the production switch and argument forwarding on
the host. --factory/--d3d12 also inspect the actual linked DLLs: x64 entries,
native targets, code-map classification and the factory's COM vtable slots.
"""
from pathlib import Path
import argparse
import importlib.util
import os
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


class PE:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        nt = self.u32(0x3c)
        assert self.data[nt:nt + 4] == b'PE\0\0', 'not a PE image'
        opt = nt + 24
        assert self.u16(opt) == 0x20b, 'not PE32+'
        self.base = self.u64(opt + 24)
        self.sections = []
        start = opt + self.u16(nt + 20)
        for i in range(self.u16(nt + 6)):
            p = start + 40 * i
            name = self.data[p:p + 8].split(b'\0')[0].decode()
            size, rva, rawsize, raw = struct.unpack_from('<IIII', self.data, p + 8)
            self.sections.append((name, rva, size, raw, rawsize, self.u32(p + 36)))
        self.symbols = {}
        sym, count = self.u32(nt + 12), self.u32(nt + 16)
        strings = sym + 18 * count
        i = 0
        while i < count:
            p = sym + 18 * i
            name = self.data[p:p + 8]
            if name[:4] == b'\0' * 4:
                q = strings + self.u32(p + 4)
                name = self.data[q:self.data.index(b'\0', q)]
            else:
                name = name.split(b'\0')[0]
            section = struct.unpack_from('<h', self.data, p + 12)[0]
            if 0 < section <= len(self.sections):
                self.symbols[name.decode()] = self.sections[section - 1][1] + self.u32(p + 8)
            i += 1 + self.data[p + 17]
        config = self.u32(opt + 112 + 10 * 8)
        meta = self.u64(self.offset(config) + 0xc8) - self.base
        m = struct.unpack_from('<20I', self.data, self.offset(meta))
        self.ranges = []
        for i in range(m[2]):
            lo, size = struct.unpack_from('<II', self.data, self.offset(m[1]) + 8 * i)
            self.ranges.append((lo & ~3, size, lo & 3))
        self.redirects = dict(struct.unpack_from('<II', self.data, self.offset(m[4]) + 8 * i)
                              for i in range(m[13]))

    def u16(self, p):
        return struct.unpack_from('<H', self.data, p)[0]

    def u32(self, p):
        return struct.unpack_from('<I', self.data, p)[0]

    def u64(self, p):
        return struct.unpack_from('<Q', self.data, p)[0]

    def offset(self, rva, length=1):
        for _, lo, _, raw, size, _ in self.sections:
            if lo <= rva and rva - lo + length <= size:
                return raw + rva - lo
        raise AssertionError(f'RVA {rva:#x}+{length:#x} has no file backing')

    def kind(self, rva):
        return next((kind for lo, size, kind in self.ranges if lo <= rva < lo + size), None)

    def entry(self, method, factory=False):
        names = [n for n in self.symbols if n.startswith('EXP+#') and
                 (('MTLDXGIHookFactory' in n and str(len(method)) + method in n)
                  if factory else n == 'EXP+#mad_x64_' + method)]
        assert len(names) == 1, f'{method}: one generated x64 entry required, found {len(names)}'
        name = names[0]
        rva = self.symbols[name]
        section = next(s for s in self.sections if s[1] <= rva < s[1] + s[2])
        assert section[0] == '.hexpthk' and section[5] & 0x20000000, f'{method}: not executable .hexpthk'
        assert self.kind(rva) == 2, f'{method}: entry must be classified x64, not native'
        p = self.offset(rva, 14)
        assert self.data[p:p + 10] == bytes.fromhex('488bc448895820555de9'), f'{method}: invalid fast-forward entry'
        target = rva + 14 + struct.unpack_from('<i', self.data, p + 10)[0]
        native = self.symbols.get(name.removeprefix('EXP+') + '$hp_target')
        assert target == native and self.kind(target) == 1, f'{method}: wrong native ABI target'
        assert self.redirects.get(rva) == target, f'{method}: missing ARM64EC redirection metadata'
        print(f'PASS {method}: x64 entry {rva:#x}, native ABI target {target:#x}')
        return rva

    def factory_slots(self, entries):
        for cls, patchable in [('MTLDXGIHookFactory', True), ('MTLDXGIFactory', False)]:
            names = [n for n in self.symbols if n.startswith('_ZTV') and n.endswith(cls + 'E')]
            assert len(names) == 1, f'{cls}: vtable missing or ambiguous'
            table = self.symbols[names[0]] + 16  # Itanium ABI offset and RTTI header
            for slot, entry in entries.items():
                rva = self.u64(self.offset(table + slot * 8, 8)) - self.base
                if patchable:
                    assert rva == entry, f'{cls}: wrong entry in COM slot {slot}'
                else:
                    assert self.kind(rva) == 1, f'{cls}: default slot {slot} must remain native'
            print(f'PASS {cls}: COM slots 8, 10 and 15 preserve the selected ABI')


def host_checks():
    spec = importlib.util.spec_from_file_location('factory_patch', ROOT / 'tools/patch-dxgi-x64-entry.py')
    patcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patcher)
    original = (ROOT / 'dxmt/src/dxgi/dxgi_factory.cpp').read_text()
    patched = patcher.patch(original)
    assert patcher.patch(patched) == patched, 'factory patch not idempotent'
    try:
        patcher.patch(original.replace('new MTLDXGIFactory(Flags)', 'new OtherFactory(Flags)'))
    except ValueError:
        pass
    else:
        raise AssertionError('changed factory allocation was silently accepted')
    print('PASS factory patch: idempotent and rejects an incompatible source')

    native = (ROOT / 'madeira-d3d12/src/pe/madeira_d3d12.c').read_text()
    wrappers = []
    for method in ['ExecuteCommandLists', 'Present', 'Present1', 'ResizeBuffers', 'ResizeBuffers1']:
        at = native.index('mad_x64_' + method + '(')
        begin = native.rfind('MAD_X64_GRAPHICS_ENTRY', 0, at)
        end = native.index('\n}', at) + 2
        wrappers.append(native[begin:end])
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef unsigned DWORD; typedef unsigned UINT; typedef int32_t HRESULT;
typedef int DXGI_FORMAT;
#define STDMETHODCALLTYPE
typedef struct obj { int unused; } IDXGISwapChain4, ID3D12CommandQueue, ID3D12CommandList, IUnknown;
typedef struct params { int unused; } DXGI_PRESENT_PARAMETERS;
static DWORD last_error = 123;
static const char *setting;
static DWORD GetLastError(void) { return last_error; }
static void SetLastError(DWORD value) { last_error = value; }
static DWORD GetEnvironmentVariableA(const char *name, char *out, DWORD cap) {
    assert(!strcmp(name, "MADEIRA_X64_GRAPHICS_ENTRY")); last_error = 999;
    if (!setting) return 0;
    DWORD n = strlen(setting); if (n >= cap) return n + 1;
    memcpy(out, setting, n + 1); return n;
}
#include "madeira_graphics_entry.h"
static IDXGISwapChain4 swap;
static ID3D12CommandQueue queue;
static ID3D12CommandList *lists[2];
static DXGI_PRESENT_PARAMETERS params;
static UINT masks[2]; static IUnknown *queues[2];
static unsigned calls;
static void queue_ExecuteCommandLists(ID3D12CommandQueue *p, UINT n, ID3D12CommandList *const *l) {
    assert(p == &queue && n == 2 && l == lists); calls++;
}
static HRESULT swap_Present(IDXGISwapChain4 *p, UINT sync, UINT flags) {
    assert(p == &swap && sync == 3 && flags == 8); calls++; return (HRESULT)0x887a0001;
}
static HRESULT swap_Present1(IDXGISwapChain4 *p, UINT sync, UINT flags, const DXGI_PRESENT_PARAMETERS *q) {
    assert(q == &params); return swap_Present(p, sync, flags);
}
static HRESULT swap_ResizeBuffers(IDXGISwapChain4 *p, UINT n, UINT w, UINT h, DXGI_FORMAT f, UINT flags) {
    assert(p == &swap && n == 3 && w == 1920 && h == 1080 && f == 87 && flags == 0x800);
    calls++; return (HRESULT)0x887a0002;
}
static HRESULT swap_ResizeBuffers1(IDXGISwapChain4 *p, UINT n, UINT w, UINT h, DXGI_FORMAT f, UINT flags,
                                  const UINT *m, IUnknown *const *q) {
    assert(m == masks && q == queues); return swap_ResizeBuffers(p, n, w, h, f, flags);
}
''' + '\n'.join(wrappers) + r'''
int main(void) {
    const char *values[] = {0, "", "0", "true", "on", "yes", "10", "1 ", "1"};
    for (unsigned i = 0; i < sizeof(values) / sizeof(values[0]); i++) {
        setting = values[i]; last_error = 123;
        assert(mad_x64_graphics_entry_enabled() == (i == 8)); assert(last_error == 123);
    }
    mad_x64_ExecuteCommandLists(&queue, 2, lists);
    assert(mad_x64_Present(&swap, 3, 8) == (HRESULT)0x887a0001);
    assert(mad_x64_Present1(&swap, 3, 8, &params) == (HRESULT)0x887a0001);
    assert(mad_x64_ResizeBuffers(&swap, 3, 1920, 1080, 87, 0x800) == (HRESULT)0x887a0002);
    assert(mad_x64_ResizeBuffers1(&swap, 3, 1920, 1080, 87, 0x800, masks, queues) == (HRESULT)0x887a0002);
    assert(calls == 5);
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        src, exe = Path(tmp) / 'h.c', Path(tmp) / 'h'
        src.write_text(code)
        subprocess.run([os.environ.get('CC', 'cc'), '-Wall', '-Werror', '-std=c11',
                        '-I' + str(ROOT / 'madeira-d3d12/src/pe'), str(src), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print('PASS production switch: default off, exact 1, LastError preserved')
    print('PASS production wrappers: all arguments and error HRESULTs preserved')


if __name__ == '__main__':
    args = argparse.ArgumentParser()
    args.add_argument('--factory')
    args.add_argument('--d3d12')
    ns = args.parse_args()
    host_checks()
    if ns.factory:
        pe = PE(ns.factory)
        pe.factory_slots({8: pe.entry('MakeWindowAssociation', True),
                          10: pe.entry('CreateSwapChain', True),
                          15: pe.entry('CreateSwapChainForHwnd', True)})
    if ns.d3d12:
        pe = PE(ns.d3d12)
        for name in ['ExecuteCommandLists', 'Present', 'Present1', 'ResizeBuffers', 'ResizeBuffers1']:
            pe.entry(name)
