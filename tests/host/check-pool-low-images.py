#!/usr/bin/env python3
"""Exercise the production small-image overflow allocator and shared C cursor.

Checks opt-in behavior, normal-pool preference, owner bookkeeping, executable
page guards, WoW64 exclusion (including reclaimed C ranges), failure atomicity,
and concurrent image/code allocations. Mach queries use synthetic clean pages;
this is an allocator test, not a device rendering test.
"""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / 'build/ntdll-unix/virtual_ios.c').read_text()


def function(signature):
    start = source.index(signature)
    return source[start:source.index('\n}', start) + 2] + '\n'


helpers = ''.join(function(signature) for signature in (
    'static size_t ios_pool_hole_head_place(',
    'static int ios_pool_low_take(',
    'static int ios_pool_best_fit(',
    'static int ios_pool_keep_big(',
    'static size_t ios_pool_alloc_range_ex(',
    'static size_t ios_pool_alloc_range(',
    'static size_t ios_pool_low_image_range(',
    'static int ios_pool_ledger_holds(',
))
image_copy = source[source.index('size_t image_alloc = (image_size + page_size - 1)'):]
image_copy = image_copy[:image_copy.index('/* Copy ENTIRE PE image')]
assert image_copy.count('ios_pool_low_image_range( alloc_size )') == 1
allocation = ('offset = ios_pool_alloc_range(alloc_size, jit_pool_size - ios_jit_tail_reserved);\n'
              '                if (offset == (size_t)-1) offset = ios_pool_low_image_range( alloc_size );')
assert allocation in image_copy, 'the overflow runs only after normal image allocation fails'
assert source.count('ios_pool_low_image_range( alloc_size )') == 1, 'anonymous RWX must retain its old path'
assert 'size_t image_used = image_in_low ? ios_jit_low_reserved : offset + alloc_size;' in source

fixture = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <pthread.h>
#include <unistd.h>
#define MB ((size_t)1 << 20)
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "failed line %d: %s\n", __LINE__, #c); exit(1); } } while (0)
#define IOS_POOL_BIG_MIN (64u * 1024 * 1024)
#define IOS_POOL_LEDGER_MAX 1024
#define IOS_POOL_FREE_MAX 256
#define IOS_POOL_REUSE_GRACE_SEC 3
struct ios_pool_free { size_t off, size; time_t freed_at; int advised; };
struct ios_pool_alloc { size_t off, size; void *peb; };
static struct ios_pool_free ios_pool_freelist[IOS_POOL_FREE_MAX];
static struct ios_pool_alloc ios_pool_ledger[IOS_POOL_LEDGER_MAX];
static int ios_pool_free_count, ios_pool_ledger_count, ios_pool_last_alloc_reused;
static size_t jit_pool_offset, ios_jit_hole_off_eff, ios_jit_hole_end_eff;
static size_t ios_pool_big_off, ios_pool_big_size, ios_jit_pool_size_global;
static int ios_pool_big_taken, wow, poisoned;
static time_t ios_pool_big_freed_at;
static pthread_mutex_t ios_pool_lock = PTHREAD_MUTEX_INITIALIZER;
static void *ios_jit_rx_base_global = (void *)(uintptr_t)0x148000000ULL;
static void *ios_jit_rw_base_global = (void *)(uintptr_t)0x791dc00000ULL;
static uintptr_t ios_jit_low_rx_global = 0x12a400000ULL;
static uintptr_t ios_jit_low_rw_global = 0x7900000000ULL;
static size_t ios_jit_low_size_global, ios_jit_tail_reserved;
static volatile size_t ios_jit_low_reserved;
static struct { uintptr_t user_va, user_va_end, jit_rw_alias; } ios_jit_anon_aliases[16];
static int ios_jit_anon_alias_count;
static _Thread_local uintptr_t owner = 1;
static void *ios_jit_current_peb(void) { return (void *)owner; }
static uintptr_t ios_wow_base(void) { return wow; }
static void ios_mono_alias_retire(uintptr_t va) { (void)va; }
static int ios_pool_range_execable(size_t off, size_t size, unsigned *cur, unsigned *max)
{ (void)off; (void)size; if (cur) *cur = 5; if (max) *max = poisoned ? 3 : 7; return !poisoned; }
static int ios_pool_range_clean(size_t off, size_t size)
{ return ios_pool_range_execable(off, size, NULL, NULL); }
static void ios_pool_check_range_exec(size_t off, size_t size, int reused)
{ (void)off; (void)size; (void)reused; }
static int ios_pool_live_overlap(uintptr_t start, size_t size, size_t *off_out, void **peb_out)
{
    size_t off = start - (uintptr_t)ios_jit_rw_base_global;
    for (int i = 0; i < ios_pool_ledger_count; i++)
        if (ios_pool_ledger[i].off < off + size && ios_pool_ledger[i].off + ios_pool_ledger[i].size > off)
        { *off_out = ios_pool_ledger[i].off; *peb_out = ios_pool_ledger[i].peb; return 1; }
    return 0;
}
typedef int (*ios_pool_region_fn)(uint64_t *, uint64_t *, unsigned *);
static int ios_pool_mach_region(uint64_t *addr, uint64_t *size, unsigned *prot)
{ (void)addr; (void)size; (void)prot; return -1; }
static int ios_pool_execable_runs(uint64_t rx, size_t off, size_t size, ios_pool_region_fn fn,
                                 size_t *ro, size_t *rs, int max)
{ (void)rx; (void)off; (void)size; (void)fn; (void)ro; (void)rs; (void)max; return 0; }
''' + helpers + r'''
static size_t image(size_t alloc_size)
{
    size_t jit_pool_size = ios_jit_pool_size_global, offset;
''' + allocation + r'''
    return offset;
}

static void reset(void)
{
    ios_jit_pool_size_global = 896 * MB;
    jit_pool_offset = ios_jit_pool_size_global;
    ios_jit_low_size_global = 348 * MB;
    ios_jit_low_reserved = 336 * MB + 0x18000;
    ios_pool_free_count = ios_pool_ledger_count = ios_jit_anon_alias_count = 0;
    ios_pool_big_size = ios_jit_hole_off_eff = ios_jit_hole_end_eff = ios_jit_tail_reserved = 0;
    wow = poisoned = 0;
    owner = 1;
}

static void no_allocation(size_t request)
{
    size_t head = jit_pool_offset, used = ios_jit_low_reserved;
    int entries = ios_pool_ledger_count;
    CHECK(image(request) == (size_t)-1);
    CHECK(jit_pool_offset == head && ios_jit_low_reserved == used);
    CHECK(ios_pool_ledger_count == entries);
}

static size_t allocations[768];
static size_t allocation_count;
static pthread_mutex_t result_lock = PTHREAD_MUTEX_INITIALIZER;
static void remember(size_t rx)
{
    pthread_mutex_lock(&result_lock);
    CHECK(allocation_count < sizeof allocations / sizeof allocations[0]);
    allocations[allocation_count++] = rx;
    pthread_mutex_unlock(&result_lock);
}
static void *allocate_images(void *arg)
{
    owner = (uintptr_t)arg;
    for (int i = 0; i < 128; i++)
    {
        size_t off = ios_pool_low_image_range(0x4000);
        if (off == (size_t)-1) continue;
        remember((uintptr_t)ios_jit_rx_base_global + off);
    }
    return NULL;
}
static void *allocate_code(void *arg)
{
    (void)arg;
    for (int i = 0; i < 256; i++)
    {
        size_t off;
        if (!ios_pool_low_take(&ios_jit_low_reserved, ios_jit_low_size_global, 0x4000, &off)) continue;
        remember(ios_jit_low_rx_global + off);
    }
    return NULL;
}

int main(void)
{
    reset();
    unsetenv("MADEIRA_POOL_LOW_IMAGES");
    no_allocation(0x378000);
    setenv("MADEIRA_POOL_LOW_IMAGES", "0", 1);
    no_allocation(0x378000);
    setenv("MADEIRA_POOL_LOW_IMAGES", "true", 1);
    no_allocation(0x378000);
    setenv("MADEIRA_POOL_LOW_IMAGES", "1", 1);
    jit_pool_offset -= 4 * MB;
    size_t used = ios_jit_low_reserved;
    CHECK(image(0x378000) < ios_jit_pool_size_global);
    CHECK(ios_jit_low_reserved == used && ios_pool_ledger_count == 1);

    reset();
    const size_t sizes[] = {0x378000, 0x13c000, 0xb4000, 0xe4000, 0x94000};
    for (size_t i = 0; i < sizeof sizes / sizeof sizes[0]; i++)
    {
        size_t previous = ios_jit_low_reserved;
        size_t off = image(sizes[i]);
        CHECK(off != (size_t)-1);
        uintptr_t rx = (uintptr_t)ios_jit_rx_base_global + off;
        CHECK(rx == ios_jit_low_rx_global + previous);
        CHECK((uintptr_t)ios_jit_rw_base_global + off == ios_jit_low_rw_global + previous);
        CHECK(ios_pool_ledger_holds(off + 0x4000, sizes[i] - 0x4000, (void *)1));
        CHECK(!ios_pool_ledger_holds(off, sizes[i], (void *)2));
        CHECK(!ios_pool_ledger_holds(off, sizes[i] + 0x4000, (void *)1));
        CHECK(jit_pool_offset == ios_jit_pool_size_global && !ios_jit_tail_reserved);
    }
    CHECK(ios_jit_low_size_global - ios_jit_low_reserved == 0x508000);
    no_allocation(2 * MB);  /* Preserve the 4 MB code-buffer reserve. */
    no_allocation(17 * MB);
    no_allocation(1);
    CHECK(ios_pool_low_image_range(0) == (size_t)-1);

    reset(); wow = 1; no_allocation(0x94000);
    reset(); ios_jit_low_size_global = 0; no_allocation(0x94000);
    reset(); ios_pool_ledger_count = IOS_POOL_LEDGER_MAX; no_allocation(0x94000);
    reset(); poisoned = 1; no_allocation(0x94000);
    reset(); ios_jit_low_reserved = ios_jit_low_size_global + MB; no_allocation(0x94000);

    /* Reclaimed C ranges obey the existing grace and never enter WoW64,
     * even when the image-overflow switch has subsequently been disabled. */
    reset();
    size_t coff = (size_t)(ios_jit_low_rx_global - (uintptr_t)ios_jit_rx_base_global);
    ios_pool_freelist[0] = (struct ios_pool_free){coff, MB, time(NULL), 1};
    ios_pool_free_count = 1;
    CHECK(ios_pool_best_fit(ios_pool_freelist, 1, 0x4000,
                           ios_pool_freelist[0].freed_at, (size_t)-1, 0) == -1);
    CHECK(ios_pool_best_fit(ios_pool_freelist, 1, 0x4000,
                           ios_pool_freelist[0].freed_at + 3, (size_t)-1, 0) == 0);
    wow = 1;
    CHECK(ios_pool_alloc_range_ex(0x4000, 0, (size_t)-1, 0) == (size_t)-1);
    CHECK(ios_pool_free_count == 1 && !ios_pool_ledger_count);
    ios_pool_freelist[0].freed_at -= 4;
    CHECK(ios_pool_alloc_range_ex(0x4000, 0, (size_t)-1, 0) == (size_t)-1);
    wow = 0;
    CHECK(ios_pool_alloc_range_ex(0x4000, 0, (size_t)-1, 0) == coff);
    CHECK(ios_pool_ledger[0].peb == (void *)1);

    reset();
    ios_pool_freelist[0] = (struct ios_pool_free){coff, MB, 0, 1};
    ios_pool_freelist[1] = (struct ios_pool_free){MB, MB, 0, 1};
    ios_pool_free_count = 2; wow = 1;
    CHECK(ios_pool_alloc_range_ex(0x4000, 0, (size_t)-1, 0) == MB);

    reset();
    ios_jit_low_reserved = 0; ios_jit_low_size_global = 12 * MB;
    allocation_count = 0;
    pthread_t workers[5];
    for (uintptr_t i = 0; i < 4; i++)
        CHECK(!pthread_create(&workers[i], NULL, allocate_images, (void *)(i + 1)));
    CHECK(!pthread_create(&workers[4], NULL, allocate_code, NULL));
    for (int i = 0; i < 5; i++) CHECK(!pthread_join(workers[i], NULL));
    CHECK(allocation_count >= 512 && allocation_count <= 768);
    CHECK(ios_jit_low_reserved == allocation_count * 0x4000);
    CHECK(ios_jit_low_reserved <= ios_jit_low_size_global);
    for (size_t i = 0; i < allocation_count; i++)
    {
        CHECK(allocations[i] >= ios_jit_low_rx_global);
        CHECK(allocations[i] + 0x4000 <= ios_jit_low_rx_global + ios_jit_low_size_global);
        for (size_t j = 0; j < i; j++) CHECK(allocations[i] != allocations[j]);
    }
    for (int i = 0; i < ios_pool_ledger_count; i++)
    {
        uintptr_t rx = (uintptr_t)ios_jit_rx_base_global + ios_pool_ledger[i].off;
        CHECK(rx + ios_pool_ledger[i].size <= ios_jit_low_rx_global + 8 * MB);
        CHECK((uintptr_t)ios_pool_ledger[i].peb >= 1 && (uintptr_t)ios_pool_ledger[i].peb <= 4);
    }
    puts("small-image overflow: opt-in, capacity, owners, WoW64 and concurrent code/image guards passed");
    return 0;
}
'''

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / 'check.c').write_text(fixture)
    command = [os.environ.get('CC', 'cc'), '-std=c11', '-D_POSIX_C_SOURCE=200809L',
               '-Wall', '-Wextra', '-Werror', '-pthread', str(path / 'check.c'), '-o', str(path / 'check')]
    if os.environ.get('SANITIZE') == '1':
        command[1:1] = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g']
    subprocess.run(command, check=True)
    result = subprocess.run([str(path / 'check')], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise SystemExit(result.stderr)
    print(result.stdout.strip())
