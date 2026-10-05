#!/usr/bin/env python3
"""Exercise the bounded message-constructor observer through the Win64 ABI.

Assemble the production hook, compare its embedded bytes, then execute it with
a logger that clobbers volatile inputs. Check original constructor arguments,
payloads, caller identity, return value, nonvolatile registers and concurrent
log limits. The external Helper binary is never executed.
"""
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
native = (root / 'build/ntdll-unix/virtual_ios.c').read_text()


def define(name):
    return int(re.search(r'#define ' + name + r'\s+(0x[\da-fA-F]+|\d+)', native)[1], 0)


start = native.index('static const unsigned char ios_sch_ui_trace[')
array = native[start:native.index('};', start) + 2]
blob = bytes(int(x, 16) for x in re.findall(r'0x([\da-fA-F]{2})', array))
symbols = {'close_count': define('IOS_SCH_UI_COUNT'), 'helper_log': 0x111340,
           'ctor_continue': define('IOS_SCH_UI_CTOR') + 5}
assert define('IOS_SCH_IPC_SPLIT') + 661 <= define('IOS_SCH_UI_TRACE')
assert define('IOS_SCH_UI_TRACE') + len(blob) <= 0x181000
assert define('IOS_SCH_IPC_CONTEXT') + 16 <= define('IOS_SCH_UI_COUNT')
assert define('IOS_SCH_UI_COUNT') + 4 <= define('IOS_SCH_CACHE')

with tempfile.TemporaryDirectory(prefix='madeira-ui-close-') as tmp:
    folder = Path(tmp)
    linker = folder / 'trace.ld'
    linker.write_text('SECTIONS { . = %d; .text : { *(.text) } }\n' % define('IOS_SCH_UI_TRACE') +
                      '\n'.join('%s = %d;' % item for item in symbols.items()) + '\n')
    subprocess.run(['as', '--64', str(root / 'tests/host/sc-ui-close.S'), '-o', str(folder / 'trace.o')], check=True)
    subprocess.run(['ld', '-T', str(linker), str(folder / 'trace.o'), '-o', str(folder / 'trace.elf')], check=True)
    subprocess.run(['objcopy', '-O', 'binary', '--only-section=.text',
                    str(folder / 'trace.elf'), str(folder / 'trace.bin')], check=True)
    assert (folder / 'trace.bin').read_bytes() == blob

    source = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdatomic.h>
#include <pthread.h>
#include <sys/mman.h>
#define ABI __attribute__((ms_abi))
struct Message { uint32_t value, canary; };
static struct Message *(ABI *entry)(struct Message *, const uint32_t *);
extern struct Message *ABI probe(struct Message *, const uint32_t *, void *);
extern struct Message *ABI ctor_tail(struct Message *, const uint32_t *);
static _Thread_local const uint32_t *expected_source;
static _Thread_local struct Message *expected_message;
static _Thread_local uintptr_t logged_caller;
static atomic_uint logs, bodies;
static void ABI logger(unsigned int level, const char *format, ...)
{
    __builtin_ms_va_list ap;
    __builtin_ms_va_start(ap, format);
    unsigned int value = __builtin_va_arg(ap, unsigned int);
    const uint32_t *source = __builtin_va_arg(ap, const uint32_t *);
    uintptr_t caller = __builtin_va_arg(ap, uintptr_t);
    __builtin_ms_va_end(ap);
    assert(!level && !strcmp(format, "[sc-ui] msg20005 value=%u source=%p caller=%p"));
    assert(source == expected_source && value == *source && caller);
    logged_caller = caller;
    atomic_fetch_add(&logs, 1);
    __asm__ volatile("xor %%ecx, %%ecx; xor %%edx, %%edx; xor %%r8d, %%r8d; xor %%r9d, %%r9d;"
                     "pxor %%xmm0, %%xmm0; pxor %%xmm1, %%xmm1; pxor %%xmm2, %%xmm2;"
                     "pxor %%xmm3, %%xmm3; pxor %%xmm4, %%xmm4; pxor %%xmm5, %%xmm5"
                     : : : "rcx", "rdx", "r8", "r9", "xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5");
}
struct Message *ABI original_ctor(struct Message *m, const uint32_t *source, uintptr_t caller)
{
    assert(m == expected_message && source == expected_source && m->canary == 0xdead1234);
    if (logged_caller) assert(logged_caller == caller);
    m->value = *source;
    atomic_fetch_add(&bodies, 1);
    return m;
}
static void stub(char *image, size_t rva, uintptr_t target)
{
    unsigned char code[12] = {0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0xe0};
    memcpy(code+2, &target, 8);
    memcpy(image+rva, code, sizeof(code));
}
static void invoke(uint32_t value)
{
    const uint32_t payload = value;
    struct Message m = {0xcccccccc, 0xdead1234};
    expected_source = &payload; expected_message = &m; logged_caller = 0;
    assert(probe(&m, &payload, entry) == &m);
    assert(m.value == value && payload == value && m.canary == 0xdead1234);
}
static void *worker(void *unused)
{
    (void)unused;
    for (unsigned i=0; i<24; i++) invoke(i);
    return NULL;
}
''' + array + r'''
int main(void)
{
    char *image = mmap(NULL, 0x244000, PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(image != MAP_FAILED);
    memcpy(image + TRACE, ios_sch_ui_trace, sizeof(ios_sch_ui_trace));
    image[CTOR] = (char)0xe9;
    int32_t displacement = TRACE - CTOR - 5;
    memcpy(image + CTOR + 1, &displacement, sizeof(displacement));
    stub(image, 0x111340, (uintptr_t)logger);
    stub(image, CTOR + 5, (uintptr_t)ctor_tail);
    assert(!mprotect(image + 0x1000, 0x180000, PROT_READ | PROT_EXEC));
    entry = (void *)(image + CTOR);
    invoke(0); invoke(1); invoke(UINT32_MAX);
    assert(logs == 3 && bodies == 3);
    pthread_t threads[6];
    for (unsigned i=0; i<6; i++) assert(!pthread_create(&threads[i], NULL, worker, NULL));
    for (unsigned i=0; i<6; i++) assert(!pthread_join(threads[i], NULL));
    assert(logs == 16 && bodies == 147 && *(unsigned int *)(image + COUNT) >= 16);
    assert(!munmap(image, 0x244000));
    puts("PASS: constructor observer retains payloads, caller, return and nonvolatile state; 147 deliveries, 16 concurrent log records");
    return 0;
}
'''
    probe = r'''
.intel_syntax noprefix
.text
.global probe
probe:
    push rbx
    push rsi
    push rdi
    sub rsp, 0x20
    mov rbx, 0x1122334455667788
    mov rsi, 0x2233445566778899
    mov rdi, 0x33445566778899aa
    call r8
    mov r9, 0x1122334455667788
    cmp rbx, r9
    jne broken
    mov r9, 0x2233445566778899
    cmp rsi, r9
    jne broken
    mov r9, 0x33445566778899aa
    cmp rdi, r9
    jne broken
    add rsp, 0x20
    pop rdi
    pop rsi
    pop rbx
    ret
broken:
    ud2
/* Model the original constructor's stack frame and RBX home-slot restore,
 * rather than letting a fresh C prologue hide a missing displaced store. */
.global ctor_tail
ctor_tail:
    push rdi
    sub rsp, 0x20
    mov rbx, rdx
    mov rdi, rcx
    mov r8, qword ptr [rsp+0x28]
    call original_ctor
    mov rbx, qword ptr [rsp+0x38]
    mov rax, rdi
    add rsp, 0x20
    pop rdi
    ret
.section .note.GNU-stack,"",@progbits
'''
    c, asm = folder / 'test.c', folder / 'probe.S'
    c.write_text(source); asm.write_text(probe)
    binary = folder / 'test'
    subprocess.run(['cc', '-std=gnu11', '-O1', '-Wall', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', '-pthread',
                    '-DTRACE=%d' % define('IOS_SCH_UI_TRACE'), '-DCTOR=%d' % define('IOS_SCH_UI_CTOR'),
                    '-DCOUNT=%d' % define('IOS_SCH_UI_COUNT'), str(c), str(asm), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    print('PASS: observer assembly matches production bytes and occupies disjoint zero tails')
