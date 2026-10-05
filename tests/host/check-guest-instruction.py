#!/usr/bin/env python3
"""Exercise production x64 section classification, IAT slots and safe snapshots.

No guest binary is executed. A two-section image exposes the old largest-only
classification; data and ARM64 targets must still translate to their copies.
"""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
native = (root / 'build/ntdll-unix/virtual_ios.c').read_text()
process = (root / 'build/ntdll-unix/process_ios.c').read_text()


def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}', start) + 2] + '\n'


first = native.index('#define IOS_JIT_MAX_MAPPINGS')
mapping = native[first:native.index('\n};', first) + 3]
functions = ''.join(function(native, signature) for signature in (
    'void ios_jit_set_text_section(',
    'static int ios_jit_code_bounds(',
    'void *ios_jit_translate_addr_for_owner(',
    'static int ios_va_is_x86_code(',
    'int ios_jit_guest_code_window(',
))
functions += function(process, 'static uint64_t ios_guest_instruction_read(')
functions += function(process, 'static void ios_dump_guest_instruction(')
loop_start = native.index('while (p < end_p)', native.index('/* ml102 FIX:'))
loop = native[loop_start:native.index('static int ml1017_said;', loop_start)]
assert 'ios_dump_guest_instruction( handle, exit_code, rip, cur_teb->Peb );' in process
assert 'ios_jit_mappings[slot].code_range_count = 0;' in native
assert 'memcpy( ios_jit_mappings[slot].code_ranges, m->code_ranges, sizeof m->code_ranges );' in native
assert 'cached = madeira_cfg_bool( "iat-noexec", 0 );' in native
assert 'if (text_size > ios_jit_mappings[i].text_size)' in functions

prefix = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
typedef void *HANDLE;
typedef int32_t LONG;
typedef uint64_t mach_vm_size_t;
typedef uintptr_t mach_vm_address_t;
#define STATUS_PRIVILEGED_INSTRUCTION ((LONG)0xc0000096u)
#define STATUS_ILLEGAL_INSTRUCTION ((LONG)0xc000001du)
#define NtCurrentProcess() ((HANDLE)(intptr_t)-1)
#define KERN_SUCCESS 0
static char output[65536];
static size_t output_size, reads;
static int empty_success;
static struct { uintptr_t low, high; } allowed[3], denied[4];
static unsigned allowed_count, denied_count;
static void permit(void *base, size_t size)
{
    assert(allowed_count < 3);
    allowed[allowed_count].low = (uintptr_t)base;
    allowed[allowed_count++].high = (uintptr_t)base + size;
}
static int fixture_mprotect(void *base, size_t size, int prot)
{
    int result = mprotect(base, size, prot);
    if (result) return result;
    if (prot == PROT_NONE)
    {
        assert(denied_count < 4);
        denied[denied_count].low = (uintptr_t)base;
        denied[denied_count++].high = (uintptr_t)base + size;
    }
    else for (unsigned i = 0; i < denied_count; i++)
        if (denied[i].low == (uintptr_t)base) denied[i].low = denied[i].high = 0;
    return 0;
}
#define mprotect fixture_mprotect
static int capture(int fd, const char *format, ...)
{
    assert(fd == 2);
    va_list args;
    va_start(args, format);
    int n = vsnprintf(output + output_size, sizeof(output) - output_size, format, args);
    va_end(args);
    assert(n >= 0 && (size_t)n < sizeof(output) - output_size);
    output_size += n;
    return n;
}
#define dprintf capture
static int mach_task_self(void) { return (int)getpid(); }
static int mach_vm_read_overwrite(int task, mach_vm_address_t address, mach_vm_size_t size,
                                  mach_vm_address_t destination, mach_vm_size_t *got)
{
    reads++;
    *got = 0;
    if (empty_success) return KERN_SUCCESS;
    assert(task == (int)getpid());
    int safe = 0;
    for (unsigned i = 0; i < allowed_count; i++)
        if (address >= allowed[i].low && address <= allowed[i].high && size <= allowed[i].high - address)
            safe = 1;
    if (!safe) return 1;
    for (unsigned i = 0; i < denied_count; i++)
        if (address < denied[i].high && address + size > denied[i].low) return 1;
    memcpy((void *)destination, (const void *)address, (size_t)size);
    *got = size;
    return KERN_SUCCESS;
}
''' + mapping + r'''
static struct ios_jit_mapping ios_jit_mappings[IOS_JIT_MAX_MAPPINGS];
static int ios_jit_mapping_count;
'''

suffix = r'''
static int sync_slots(uint64_t *slots, size_t count, void *sync_owner)
{
    uint64_t *p = slots, *end_p = slots + count;
    int x86skip = 0, execskip = 0, fixup_count = 0, region_is_exec = 0;
    uint64_t x86_first = 0, exec_first = 0;
''' + loop + r'''
    (void)x86_first; (void)exec_first;
    return fixup_count;
}
static void map(unsigned i, void *pe, void *copy, void *owner, unsigned machine)
{
    struct ios_jit_mapping *m = &ios_jit_mappings[i];
    memset(m, 0, sizeof(*m));
    m->pe_base = pe; m->jit_base = copy; m->size = 0x8000;
    m->owner_peb = owner; m->machine_valid = 1; m->machine_cached = machine;
    if ((int)i >= ios_jit_mapping_count) ios_jit_mapping_count = (int)i + 1;
}
static void reset_output(void) { output_size = reads = 0; output[0] = 0; }
int main(int argc, char **argv)
{
    assert(argc == 2);
    const size_t page = (size_t)sysconf(_SC_PAGESIZE);
    assert(page == 4096);
    unsigned char *pe = mmap(NULL, 0x8000, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    unsigned char *parent = mmap(NULL, 0x8000, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    unsigned char *child = mmap(NULL, 0x8000, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(pe != MAP_FAILED && parent != MAP_FAILED && child != MAP_FAILED);
    permit(pe, 0x8000); permit(parent, 0x8000); permit(child, 0x8000);
    for (unsigned i = 0; i < 0x8000; i++) pe[i] = (unsigned char)i;
    memcpy(parent, pe, 0x8000); memcpy(child, pe, 0x8000);
    void *owner = (void *)0x4560;
    map(0, pe, parent, NULL, 0x8664);
    ios_jit_set_text_section(pe, 0x1000, 0x1000);
    ios_jit_set_text_section(pe, 0x4000, 0x2000);
    ios_jit_set_text_section(pe, 0x1000, 0x1000); /* duplicate load notification */
    struct ios_jit_mapping *m = &ios_jit_mappings[0];
    assert(m->code_range_count == 2 && m->text_offset == 0x4000 && m->text_size == 0x2000);
    map(1, pe, child, owner, 0x8664);
    ios_jit_mappings[1].code_range_count = m->code_range_count;
    memcpy(ios_jit_mappings[1].code_ranges, m->code_ranges, sizeof(m->code_ranges));
    uintptr_t b = (uintptr_t)pe;
    if (!strcmp(argv[1], "targets"))
    {
        uint64_t slots[] = {b + 0x1100, b + 0x4100, b + 0x3000, 0, 0x9999};
        assert(sync_slots(slots, 5, owner) == 1);
        assert(slots[0] == b + 0x1100 && slots[1] == b + 0x4100);
        assert(slots[2] == (uintptr_t)child + 0x3000 && slots[3] == 0 && slots[4] == 0x9999);
        assert(ios_va_is_x86_code(b + 0x1000) && ios_va_is_x86_code(b + 0x1fff));
        assert(!ios_va_is_x86_code(b + 0x2000) && !ios_va_is_x86_code(b + 0x3fff));
        assert(ios_va_is_x86_code(b + 0x4000) && ios_va_is_x86_code(b + 0x5fff));
        assert(!ios_va_is_x86_code(b + 0x6000));
        m->machine_cached = 0xaa64;
        slots[0] = b + 0x1100;
        assert(sync_slots(slots, 1, owner) == 1 && slots[0] == (uintptr_t)child + 0x1100);
        m->machine_cached = 0x8664;
        m->code_range_count = 0; /* compatibility with an older/partial registry */
        assert(!ios_va_is_x86_code(b + 0x1100) && ios_va_is_x86_code(b + 0x4100));
        m->machine_valid = 0;
        uint32_t lfanew = 0x80; uint16_t machine = 0x8664;
        memcpy(pe + 0x3c, &lfanew, 4); memcpy(pe + lfanew + 4, &machine, 2);
        reads = 0;
        assert(ios_va_is_x86_code(b + 0x4100) && reads == 2);
        assert(ios_va_is_x86_code(b + 0x4101) && reads == 2); /* header memoization */
        m->machine_valid = 0;
        assert(!mprotect(pe, page, PROT_NONE));
        assert(!ios_va_is_x86_code(b + 0x4100));
        assert(!mprotect(pe, page, PROT_READ | PROT_WRITE));
        puts("PASS: real IAT loop preserves both x64 code sections; data/ARM64 and owner routing remain intact");
    }
    else if (!strcmp(argv[1], "snapshot"))
    {
        uint64_t image = 0, start = 0; size_t length = 0;
        assert(ios_jit_guest_code_window(b + 0x1001, &image, &start, &length));
        assert(image == b && start == b + 0x1000 && length == 33);
        assert(ios_jit_guest_code_window(b + 0x1fff, &image, &start, &length));
        assert(start == b + 0x1fef && length == 17);
        assert(!ios_jit_guest_code_window(b + 0x2000, &image, &start, &length));
        m->unmapped = 1; ios_jit_mappings[1].unmapped = 1;
        assert(!ios_jit_guest_code_window(b + 0x1100, &image, &start, &length));
        m->unmapped = 0; ios_jit_mappings[1].unmapped = 0;
        size_t low, high;
        struct ios_jit_mapping malformed = *m;
        malformed.code_ranges[0].offset = SIZE_MAX - 10;
        malformed.code_ranges[0].size = 100;
        assert(!ios_jit_code_bounds(&malformed, 0x1100, &low, &high));
        malformed.code_range_count = IOS_JIT_MAX_CODE_RANGES + 1;
        assert(!ios_jit_code_bounds(&malformed, 0x1100, &low, &high));
        memset(malformed.code_ranges, 0, sizeof(malformed.code_ranges));
        malformed.code_range_count = IOS_JIT_MAX_CODE_RANGES;
        assert(ios_jit_code_bounds(&malformed, 0x4100, &low, &high)); /* largest-field fallback */
        reset_output();
        ios_dump_guest_instruction(NtCurrentProcess(), 161, b + 0x1100, owner);
        ios_dump_guest_instruction((HANDLE)0x88, STATUS_PRIVILEGED_INSTRUCTION, b + 0x1100, owner);
        assert(!reads && !output_size);
        child[0x1100] ^= 1;
        ios_dump_guest_instruction(NtCurrentProcess(), STATUS_PRIVILEGED_INSTRUCTION, b + 0x1100, owner);
        assert(strstr(output, "rva=0x1100") && strstr(output, "opcode-offset=16"));
        assert(strstr(output, "snapshot=DIFFER") && reads == 96);
        assert(!memcmp(parent, pe, 0x8000)); /* parent copy must not supply the snapshot */
        child[0x1100] ^= 1;
        reset_output();
        ios_dump_guest_instruction(NtCurrentProcess(), STATUS_ILLEGAL_INSTRUCTION, b + 0x1100, owner);
        assert(strstr(output, "snapshot=MATCH"));
        reset_output();
        assert(!mprotect(child + 0x1000, page, PROT_NONE));
        ios_dump_guest_instruction(NtCurrentProcess(), STATUS_PRIVILEGED_INSTRUCTION, b + 0x1fff, owner);
        assert(strstr(output, "snapshot=INCOMPLETE") && strstr(output, "??"));
        assert(reads == 34); /* clipped to this section, no access into .data */
        assert(!mprotect(child + 0x1000, page, PROT_READ | PROT_WRITE));
        reset_output(); empty_success = 1;
        ios_dump_guest_instruction(NULL, STATUS_PRIVILEGED_INSTRUCTION, b + 0x1100, owner);
        assert(strstr(output, "snapshot=INCOMPLETE"));
        empty_success = 0;
        reset_output();
        for (unsigned i = 0; i < 64; i++)
            ios_dump_guest_instruction(NULL, STATUS_PRIVILEGED_INSTRUCTION, b + 0x1100, owner);
        assert(reads == 12 * 96); /* first four reports consumed above; 16 total */
        reset_output(); unsigned char unused[48] = {0};
        assert(!ios_guest_instruction_read("invalid", UINT64_MAX - 2, 48, unused));
        assert(!ios_guest_instruction_read("invalid", b, 49, unused));
        assert(!reads && !output_size);
        puts("PASS: clipped code-only snapshots, correct child copy, inaccessible/short reads, bounded output and no guest mutation");
    }
    else abort();
    assert(!munmap(pe, 0x8000) && !munmap(parent, 0x8000) && !munmap(child, 0x8000));
    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='guest-instruction-') as directory:
    folder = Path(directory)
    code = prefix + functions + suffix
    cc = os.environ.get('CC', 'cc')
    flags = ['-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
             '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1')
    unit = folder / 'check.c'
    unit.write_text(code)
    binary = folder / 'check'
    subprocess.run([cc, *flags, str(unit), '-o', str(binary)], check=True)
    for case in ('targets', 'snapshot'):
        subprocess.run([str(binary), case], env=env, check=True)
    legacy = 'if (!ios_jit_code_bounds( &ios_jit_mappings[i], off, &t_off, &t_sz )) return 0;'
    assert code.count(legacy) == 1
    unit.write_text(code.replace(legacy, '''t_off = ios_jit_mappings[i].text_offset;
        t_sz = ios_jit_mappings[i].text_size;
        if (!t_sz || off < t_off || off >= t_off + t_sz) return 0;'''))
    subprocess.run([cc, *flags, str(unit), '-o', str(binary)], check=True)
    failed = subprocess.run([str(binary), 'targets'], env=env, capture_output=True, text=True)
    assert failed.returncode != 0 and 'sync_slots(slots, 5, owner) == 1' in failed.stderr, failed.stderr
    print('PASS: negative control rejects the original largest-only classification')
