#!/usr/bin/env python3
"""Social Club helper restarts and layout 2 in virtual_ios.c; no Wine runs.

GTA V Enhanced log 2026-10-02 18:24 (build 337): the game started SocialClubHelper.exe 19
times. The first died in libcef.dll's PartitionAlloc (jumbo#3: 32 GB at a 32 GB boundary,
soft grant 0x7400000000, FreePages -> STATUS_FREE_VM_NOT_AT_BASE). Helpers 2-19 never got
that far: first-fit carved their small images (20 of 51 ranges came back POISONED) out of
the dead helper's 239 MB libcef.dll range, so libcef.dll was EXHAUSTED for every one of them.

Compiles the production helpers (ios_pool_best_fit, ios_pool_keep_big, ios_pool_free_put,
ios_pool_execable_runs, ios_sc_layout_pick, ios_sc2_classify and the layout 2 constants)
and checks:
  - best-fit picks the smallest grace-expired range in reach and leaves a big range to a
    big image while the bump has room; freed ranges merge with clean neighbours, a
    POISONED one goes on as its executable runs. In a model of 19 helper restarts with
    one page poisoned in every other small image each time, the old first-fit refuses
    libcef.dll from the second helper on (as on the device) and the new policy serves all 19;
  - env.MADEIRA_SC_PA_POOLS 0/1/2 and the RW alias base pick the layout;
  - the helper's NtAllocateVirtualMemory asks in order (chrome_elf PA, its 16 GB metadata
    region, libcef PA, its metadata region -- build 340 log -- then Oilpan, which Chromium 142's
    Blink reserves BEFORE V8 initialises) get E, J2, L, J2L, Oilpan; a fourth 32 GB block is
    refused, and an 8 / 16 GB ask (4 GB-aligned hint) never takes a slot;
  - the layout 2 address map: both PartitionAlloc blocks on 32 GB boundaries, Oilpan at
    chrome_elf's block + 16 GB, both metadata regions (8 GB real of 16) in libcef's BRP
    half, alias / cage / Oilpan / FEX arena disjoint up to 0x8000000000;
  - ios_sc2_commit_class: a furniture commit (the boot false alarm of build 340) says
    nothing; metadata page commits name a super page near / past a pool's real 4 GB or in
    the BRP pool; a commit in a grant's given-but-unreserved part outside every real view
    is reported;
and textually: the hooks in NtAllocateVirtualMemory / NtFreeVirtualMemory /
ios_jit_reclaim_process / virtual_init and the app's alias placement.
Needs python3 and a C compiler (AddressSanitizer/UBSan).
"""
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
native = (root / 'build/ntdll-unix/virtual_ios.c').read_text()
swift = (root / 'app/Madeira/StikJITHelper.swift').read_text()


def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}', start) + 2] + '\n'


def defines(prefix):
    return ''.join(m.group(0) + '\n' for m in re.finditer(r'^#define ' + prefix + r'\w+\s+\S+', native, re.M))


struct = native[native.index('struct ios_pool_free\n{'):]
struct = struct[:struct.index('};') + 2] + '\n'
enum = native[native.index('enum { IOS_SC2_NONE,'):]
enum = enum[:enum.index(';') + 1] + '\n'
cclass = native[native.index('enum { IOS_SC2_C_OK,'):]
cclass = cclass[:cclass.index('};', cclass.index('struct ios_sc2_gv')) + 2] + '\n'
runs_typedef = native[native.index('typedef int (*ios_pool_region_fn)'):]
runs_typedef = runs_typedef[:runs_typedef.index(';') + 1] + '\n'
clean_typedef = native[native.index('typedef int (*ios_pool_clean_fn)'):]
clean_typedef = clean_typedef[:clean_typedef.index(';') + 1] + '\n'
helpers = runs_typedef + clean_typedef + ''.join(function(native, sig) for sig in (
    'static int ios_pool_execable_runs(',
    'static int ios_pool_free_put(',
    'static int ios_pool_best_fit(',
    'static int ios_pool_keep_big(',
    'static int ios_sc_layout_pick(',
    'static int ios_sc2_classify(',
    'static int ios_sc2_commit_class(',
))

# --- call sites ---------------------------------------------------------------
alloc = native[native.index('static size_t ios_pool_alloc_range_ex('):]
alloc = alloc[:alloc.index('\n}\n')]
assert 'while ((i = ios_pool_best_fit( ios_pool_freelist, ios_pool_free_count, alloc_size, now,' in alloc
assert 'i--;' not in alloc[alloc.index('ios_pool_best_fit('):], 'a dropped entry is re-picked, not skipped'
loop = alloc[alloc.index('while ((i = ios_pool_best_fit('):]
assert loop.index('if (ios_pool_keep_big( ios_pool_freelist[i].size, alloc_size, bump_ok ))') \
    < loop.index('ios_pool_range_execable('), 'a kept range is not salvaged first'
assert 'bump_ok = bump_cand + alloc_size <= pool_limit && IOS_POOL_IN_REACH(bump_cand);' in alloc
bump = alloc[alloc.index('if (off == (size_t)-1)'):]
assert 'size_t cand = ios_pool_hole_head_place( jit_pool_offset, alloc_size,' in bump
assert 'if (cand + alloc_size <= pool_limit\n            && IOS_POOL_IN_REACH(cand))' in bump, 'bump_ok mirrors the bump'

nt = native[native.index('NTSTATUS WINAPI NtAllocateVirtualMemory( HANDLE process'):]
nt = nt[:nt.index('NTSTATUS WINAPI NtAllocateVirtualMemoryEx(')]
assert 'if (is_jumbo && ios_sc_grant_dead_n && ios_sc_cef_enabled() && ios_sc_current_is_helper())' in nt
assert nt.index('ios_sc_reap_dead();') < nt.index('ios_sc2_route(')
assert 'if (sc2 && ios_sc2_route( hint, *size_ptr, type, protect, &pick, &sz, &st2 ))' in nt
assert nt.index('goto sc_decided;') < nt.index('sc_decided:') < nt.index('[jumbo] hinted reserve %p')
assert '!sc2 && sc_helper && *size_ptr == 0x800000000ULL' in nt, 'layout 1 keeps ios_sc_glued_pools'
assert "&& *size_ptr >= 0x400000000ULL && !sc_helper)" in nt, 'no soft grant for the helper'
assert "*size_ptr == 0x100000000ULL && !sc_helper)" in nt, 'no soft 4 GB cage for the helper'
assert 'ios_sc_grant_note( *ret, *size_ptr );' in nt and 'ios_sc2_note_commit( *ret, *size_ptr );' in nt
note = function(native, 'static void ios_sc2_note_commit(')
assert 'if (a < IOS_SC2_L_BASE || !ios_sc_grant_n || !ios_sc_current_is_helper()) return;' in note, \
    'only SocialClubHelper.exe commits are judged'
assert 'if (ios_sc_grants[i].peb != peb || ios_sc_grants[i].dead) continue;' in note, 'only its own live grants'
route = function(native, 'static int ios_sc2_route(')
assert 'ios_sc_grant_add( base, report, s, size, k, peb );' in route
assert 'ios_sc_grant_has( peb, IOS_SC2_E ),\n                              ios_sc_grant_has( peb, IOS_SC2_L ), ' \
       'ios_sc_grant_has( peb, IOS_SC_K_CAGE ) );' in route, 'Oilpan needs both PartitionAlloc blocks, not the cage'

free = function(native, 'NTSTATUS WINAPI NtFreeVirtualMemory(')
assert 'if (ios_sc_grant_release( base, &served, &sc_rehold ))' in free
assert free.index('ios_sc_grant_release(') < free.index('server_enter_uninterrupted_section( &virtual_mutex')
assert free.index('server_leave_uninterrupted_section') < free.index('ios_sc_rehold( sc_rehold )')

reclaim = function(native, 'void ios_jit_reclaim_process( void *peb )')
assert reclaim.index('ios_sc_grants_owner_died( peb );') < reclaim.index('if (!peb || !rx_base) return;')
assert 'if (!ios_pool_range_clean( off, size ))' in reclaim
assert 'nr = ios_pool_execable_runs( (uint64_t)(uintptr_t)rx_base, off, size, ios_pool_mach_region,' in reclaim
assert 'r_off[r], r_size[r], time( NULL ), ios_pool_range_clean ))' in reclaim
assert 'ios_pool_freelist[ios_pool_free_count].off = off;' not in reclaim, 'every freed range goes through ios_pool_free_put'

init = function(native, 'void virtual_init(void)')
assert init.index('ios_sc2_boot_holds();') < init.index('if (ios_sc_layout_mode == 2) ios_cage_base = IOS_SC2_CAGE_BASE;') \
    < init.index('anon_mmap_fixed( (void *)(uintptr_t)IOS_CAGE_BASE')
floor = function(native, 'static inline ULONG_PTR ios_usable_va_floor_get(void)')
assert 'if (ios_sc_layout_mode == 2) return (ULONG_PTR)0x7100000000ULL;' in floor
glued = function(native, 'static NTSTATUS ios_sc_glued_pools(')
assert 'ios_sc_grant_add( IOS_SC_GLUED_BASE, IOS_SC_GLUED_BASE, lsz, IOS_SC_GLUED_SIZE, IOS_SC_K_V1, ios_jit_current_peb() );' in glued
boot = function(native, 'static void ios_sc2_boot_holds(void)')
assert boot.count('for (k = IOS_SC2_E; k <= IOS_SC2_OILPAN; k++)') == 2, 'every slot is held at boot'
assert 'if (kind >= IOS_SC2_E && kind <= IOS_SC2_OILPAN)' in function(native, 'static void ios_sc_rehold( int kind )')
reap = function(native, 'static void ios_sc_reap_dead( void )')
assert '(uint64_t)(ULONG_PTR)mbi.AllocationBase == view' in reap, 'only a view that still starts there is freed'
print('PASS: hooks in the pool allocator, NtAllocateVirtualMemory, NtFreeVirtualMemory, reclaim and virtual_init')

assert 'static let scLayout2Alias: vm_address_t = 0x7900000000' in swift
assert swift.count('rwAliasHint()') == 3 and swift.count('!rwAliasKeep(') == 2
assert 'MadeiraConfig.gameValue("env.MADEIRA_SC_PA_POOLS") ?? MadeiraConfig.get("env.MADEIRA_SC_PA_POOLS")' in swift
assert 'guard v.hasPrefix("2") else { return 0x7000000000 }' in swift
print('PASS: the app moves the RW alias and holds 0x7000000000 only for env.MADEIRA_SC_PA_POOLS = 2')

harness = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#define IOS_POOL_REUSE_GRACE_SEC 3
''' + struct + defines('IOS_SC2_') + defines('IOS_SC_') + enum + cclass + helpers + r'''
#define MB ((size_t)1 << 20)
#define GB (1ull << 30)
#define FAIL(...) do { fprintf(stderr, __VA_ARGS__); exit(1); } while (0)

/* --- pool model: bump head + freelist with the production pick, put and salvage --- */
static struct ios_pool_free fl[256];
static int nfl, lost, old_policy;
static size_t head, limit;
static struct { size_t off, size; } led[256];
static int nled;
static size_t bad[4096];   /* poisoned 16 KB pages (pool offsets); poison is for good */
static int nbad;

static int is_bad( size_t page ) { int i; for (i = 0; i < nbad; i++) if (bad[i] == page) return 1; return 0; }

static int clean( size_t off, size_t size )
{
    int i;
    for (i = 0; i < nbad; i++) if (bad[i] >= off && bad[i] < off + size) return 0;
    return 1;
}

/* mach_vm_region over a pool at base 0: a poisoned page is a 16 KB RW region,
 * everything else executable up to the next poisoned page */
static int region( uint64_t *addr, uint64_t *size, unsigned int *max_prot )
{
    size_t a = (size_t)*addr & ~(size_t)0x3fff, next = (size_t)1 << 40;
    int i;
    if (is_bad( a )) { *addr = a; *size = 0x4000; *max_prot = 3; return 0; }
    for (i = 0; i < nbad; i++) if (bad[i] > a && bad[i] < next) next = bad[i];
    *addr = a; *size = next - a; *max_prot = 7;
    return 0;
}

static void fl_add_old( size_t off, size_t size, int advised )   /* the old append */
{
    if (nfl >= 256) { lost++; return; }
    fl[nfl].off = off; fl[nfl].size = size; fl[nfl].freed_at = 0; fl[nfl].advised = advised; nfl++;
}

static int load( size_t size )
{
    for (;;)
    {
        int i, pick = -1;
        if (!old_policy) pick = ios_pool_best_fit( fl, nfl, size, 100, (size_t)-1, 0 );
        else
            for (i = 0; i < nfl; i++) if (fl[i].size >= size) { pick = i; break; }   /* the old first-fit */
        if (pick < 0) break;
        if (!old_policy && ios_pool_keep_big( fl[pick].size, size, head + size <= limit )) break;
        if (!clean( fl[pick].off, fl[pick].size ))   /* the hand-out salvage, as in ios_pool_alloc_range_ex */
        {
            struct ios_pool_free b = fl[pick];
            size_t ro[16], rs[16];
            int r, n = (b.advised & 2) ? 0 : ios_pool_execable_runs( 0, b.off, b.size, region, ro, rs, 16 );
            fl[pick] = fl[--nfl];
            for (r = 0; r < n; r++) fl_add_old( ro[r], rs[r], b.advised | 2 );
            continue;
        }
        led[nled].off = fl[pick].off; led[nled].size = size; nled++;
        if (fl[pick].size > size) { fl[pick].off += size; fl[pick].size -= size; }
        else fl[pick] = fl[--nfl];
        return 1;
    }
    if (head + size > limit) return 0;
    led[nled].off = head; led[nled].size = size; nled++;
    head += size;
    return 1;
}

/* ios_jit_reclaim_process: ledger order 0, n-1, n-2, ... (swap-with-last). Every
 * other small image comes back with one page POISONED (20 of 51 ranges did in the
 * 18:24 log), always in a new place. */
static void die( void )
{
    int i, k = 0;
    for (i = 0; i < nled; i++)
    {
        int j = i ? nled - i : 0;
        size_t off = led[j].off, size = led[j].size;
        if (size < 32 * MB && (k++ & 1) && nbad < 4096)
        {
            bad[nbad] = off + ((size / 2 + 0x4000 * (size_t)(nbad % 3)) & ~(size_t)0x3fff);
            nbad++;
        }
        if (old_policy) { fl_add_old( off, size, 0 ); continue; }
        {
            size_t ro[16], rs[16];
            int r, n = 1;
            ro[0] = off; rs[0] = size;
            if (!clean( off, size )) n = ios_pool_execable_runs( 0, off, size, region, ro, rs, 16 );
            for (r = 0; r < n; r++)
                if (!ios_pool_free_put( fl, &nfl, 256, ro[r], rs[r], 0, clean )) lost++;
        }
    }
    nled = 0;
}

/* SocialClubHelper.exe's images in load order (sizes as copied, 18:24 log), libcef.dll 10th */
static const size_t imgs[] = { 0x2c4000, 0x414000, 0x134000, 0xc4000, 0x2f4000, 0x224000, 0xf4000, 0xb4000,
                               0x84000, 0xefc0000, 0x124000, 0x94000, 0x84000, 0x94000, 0x94000, 0xa4000,
                               0xb4000, 0xa4000, 0x134000, 0x1d4000, 0xe4000, 0x134000, 0xa4000, 0x184000,
                               0x84000, 0x164000, 0xb4000, 0x94000, 0x84000, 0x25c000, 0x84000 };
#define NIMG (sizeof(imgs) / sizeof(imgs[0]))

static int helper( void )   /* the image that failed, -1 if none */
{
    unsigned i;
    for (i = 0; i < NIMG; i++) if (!load( imgs[i] )) return (int)i;
    return -1;
}

/* 19 helpers in a row on the 18:24 pool (99 MB between head and tail after the
 * first); returns how many loaded everything, *first_fail = the first failing image */
static int run19( int old, size_t all, int *first_fail )
{
    int h, ok = 0;
    old_policy = old;
    head = 0; nfl = 0; nled = 0; lost = 0; nbad = 0; *first_fail = -1;
    limit = all + 99 * MB;
    for (h = 0; h < 19; h++)
    {
        int r = helper();
        if (r == -1) ok++;
        else if (*first_fail == -1) *first_fail = r;
        die();
    }
    return ok;
}

int main( void )
{
    struct ios_pool_free t[4];

    /* best-fit basics */
    memset( t, 0, sizeof(t) );
    t[0] = (struct ios_pool_free){ 0x100000, 0x800000, 0, 0 };
    t[1] = (struct ios_pool_free){ 0x900000, 0x40000, 0, 0 };
    t[2] = (struct ios_pool_free){ 0xa00000, 0x40000, 0, 0 };
    t[3] = (struct ios_pool_free){ 0xb00000, 0x20000, 99, 0 };   /* still in its grace */
    if (ios_pool_best_fit( t, 4, 0x40000, 100, (size_t)-1, 0 ) != 1) FAIL("smallest fit, first of equals\n");
    if (ios_pool_best_fit( t, 4, 0x10000, 100, (size_t)-1, 0 ) != 1) FAIL("a range in its grace was picked\n");
    if (ios_pool_best_fit( t, 4, 0x10000, 103, (size_t)-1, 0 ) != 3) FAIL("grace-expired smallest not picked\n");
    if (ios_pool_best_fit( t, 4, 0x900000, 100, (size_t)-1, 0 ) != -1) FAIL("nothing fits\n");
    if (ios_pool_best_fit( t, 4, 0x40000, 100, 0x100000, 0x200000 ) != 0) FAIL("reach ignored\n");
    if (ios_pool_best_fit( t, 0, 0x4000, 100, (size_t)-1, 0 ) != -1) FAIL("empty list\n");
    if (ios_pool_keep_big( 0xefc0000, 0x94000, 0 ) || !ios_pool_keep_big( 0xefc0000, 0x94000, 1 )
        || ios_pool_keep_big( 0xefc0000, 0xefc0000, 1 ) || ios_pool_keep_big( 16 * MB, 0x94000, 1 ))
        FAIL("keep_big\n");
    printf("PASS: best-fit takes the smallest grace-expired range in reach; a 32 MB+ range 4x the ask is kept "
           "while the bump has room\n");

    {
        size_t all = 0;
        unsigned i;
        int ff_ok, bf_ok, ff_fail, bf_fail;
        for (i = 0; i < NIMG; i++) all += imgs[i];
        ff_ok = run19( 1, all, &ff_fail );
        bf_ok = run19( 0, all, &bf_fail );
        printf("      first-fit: %d of 19 helpers load everything (first failure: image %d); best-fit: %d of 19 "
               "(bump 0x%zx of 0x%zx, %d ranges listed, %d lost)\n", ff_ok, ff_fail, bf_ok, head, limit, nfl, lost);
        if (ff_fail != 9) FAIL("first-fit did not fail at libcef.dll first (%d)\n", ff_fail);
        if (bf_ok != 19) FAIL("best-fit: only %d of 19 helpers loaded everything (first failure %d)\n", bf_ok, bf_fail);
        printf("PASS: first-fit refuses a restarted helper's libcef.dll, as on the device; best-fit with merging serves all 19\n");
    }

    /* layout pick */
    if (ios_sc_layout_pick( NULL, IOS_SC2_RW_ALIAS, 0x38000000 ) != 0) FAIL("unset\n");
    if (ios_sc_layout_pick( "0", IOS_SC2_RW_ALIAS, 0x38000000 ) != 0) FAIL("0\n");
    if (ios_sc_layout_pick( "1", 0x7000000000ull, 0x38000000 ) != 1) FAIL("1\n");
    if (ios_sc_layout_pick( "2", IOS_SC2_RW_ALIAS, 0x38000000 ) != 2) FAIL("2\n");
    if (ios_sc_layout_pick( "2", 0x7000000000ull, 0x38000000 ) != 1) FAIL("2 without the alias moved\n");
    if (ios_sc_layout_pick( "2", IOS_SC2_RW_ALIAS, IOS_SC2_RW_MAX + 0x4000 ) != 1) FAIL("2 with the alias into the cage\n");
    printf("PASS: env.MADEIRA_SC_PA_POOLS 0/1/2; 2 only with the RW alias at 0x%llx\n", IOS_SC2_RW_ALIAS);

    /* the helper's asks, in order */
    {
        unsigned held = (1u << IOS_SC2_E) | (1u << IOS_SC2_L) | (1u << IOS_SC2_J2) | (1u << IOS_SC2_J2L)
                        | (1u << IOS_SC2_OILPAN);
        int e = 0, l = 0, cage = 0, k;
        if (ios_sc2_classify( 32 * GB, 0x2d5800000000ull, held, e, l, cage ) != IOS_SC2_E) FAIL("chrome_elf PA\n");
        held &= ~(1u << IOS_SC2_E); e = 1;
        /* a 32 GB ask between chrome_elf's and libcef's blocks is libcef's, never Oilpan's */
        if (ios_sc2_classify( 32 * GB, 0x67d000000000ull, held | (1u << IOS_SC2_OILPAN), e, l, cage ) != IOS_SC2_L)
            FAIL("second block\n");
        if (ios_sc2_classify( 16 * GB, 0x6ce965050000ull, held, e, l, cage ) != IOS_SC2_J2) FAIL("chrome_elf metadata\n");
        held &= ~(1u << IOS_SC2_J2);
        if (ios_sc2_classify( 32 * GB, 0x67d000000000ull, held, e, l, cage ) != IOS_SC2_L) FAIL("libcef PA\n");
        held &= ~(1u << IOS_SC2_L); l = 1;
        /* build 340, jumbo#4: libcef's metadata region at an unaligned random hint */
        if (ios_sc2_classify( 16 * GB, 0x2fd6ce670000ull, held, e, l, cage ) != IOS_SC2_J2L) FAIL("libcef metadata\n");
        if (ios_sc2_classify( 16 * GB, 0, held, e, l, cage ) != IOS_SC2_NONE) FAIL("hint 0 took a metadata slot\n");
        if (ios_sc2_classify( 16 * GB, 0x2fd6ce670000ull, held, e, l, 1 ) != IOS_SC2_NONE)
            FAIL("a metadata slot after the V8 cage\n");
        held &= ~(1u << IOS_SC2_J2L);
        if (ios_sc2_classify( 16 * GB, 0x2fd6ce670000ull, held, e, l, cage ) != IOS_SC2_NONE) FAIL("a third metadata region\n");
        /* Chromium 142: Blink's ProcessHeap::Init reserves Oilpan's cage (cppgc caged-heap.cc: 4 tries
         * of 32 GB at a random 32 GB-aligned hint) BEFORE V8::Initialize -- no V8 cage yet */
        k = ios_sc2_classify( 32 * GB, 0x1000000000ull, held, e, l, cage );
        if (k != IOS_SC2_OILPAN) FAIL("Oilpan before the V8 cage: %d (the old rule refused it)\n", k);
        held &= ~(1u << IOS_SC2_OILPAN);
        /* cppgc's other tries / a fourth block: refused */
        if (ios_sc2_classify( 32 * GB, 0x1000000000ull, held, e, l, cage ) != IOS_SC2_REFUSE) FAIL("a fourth block\n");
        if (ios_sc2_classify( 32 * GB, 0x1000000000ull, held, e, l, 1 ) != IOS_SC2_REFUSE) FAIL("a fourth block, cage\n");
        /* V8 reserves through VirtualAlloc2 (NtAllocateVirtualMemoryEx), which never classifies; were one of
         * its steps to come here, nothing but 32 GB at a 32 GB boundary is decided */
        if (ios_sc2_classify( 8 * GB, 0x3f00000000ull, held, e, l, cage ) != IOS_SC2_NONE) FAIL("8 GB classified\n");
        if (ios_sc2_classify( 16 * GB, 0x3f00000000ull, held, e, l, cage ) != IOS_SC2_NONE) FAIL("16 GB classified\n");
        if (ios_sc2_classify( 32 * GB, 0x1000000000ull, (1u << IOS_SC2_OILPAN), 0, 1, 1 ) != IOS_SC2_REFUSE)
            FAIL("Oilpan for a helper without chrome_elf's block\n");
        if (ios_sc2_classify( 32 * GB, 0x1000000000ull, (1u << IOS_SC2_OILPAN), 1, 0, 0 ) != IOS_SC2_REFUSE)
            FAIL("Oilpan for a helper without libcef's block (another helper's)\n");
        if (ios_sc2_classify( 16 * GB, 0x1234560000ull, (1u << IOS_SC2_J2) | (1u << IOS_SC2_E), 0, 0, 0 ) != IOS_SC2_NONE)
            FAIL("16 GB before chrome_elf's PA took J2\n");
        /* chrome_elf's PartitionAlloc without a metadata region: libcef's still gets J2L */
        if (ios_sc2_classify( 16 * GB, 0x2fd6ce670000ull, (1u << IOS_SC2_J2) | (1u << IOS_SC2_J2L) | (1u << IOS_SC2_OILPAN),
                              1, 1, 0 ) != IOS_SC2_J2L)
            FAIL("libcef's metadata when chrome_elf asked for none\n");
        printf("PASS: chrome_elf PA -> 0x%llx, its metadata -> 0x%llx, libcef PA -> 0x%llx, its metadata -> 0x%llx, "
               "Oilpan -> view 0x%llx as the third 32 GB block, before the V8 cage; a fourth is refused\n",
               IOS_SC2_E_BASE, IOS_SC2_J2_BASE, IOS_SC2_L_BASE, IOS_SC2_J2L_BASE, IOS_SC2_OILPAN_BASE);
    }

    /* the address map */
    {
        const unsigned long long B32 = 32 * GB, top = 0x8000000000ull;
        if (IOS_SC2_L_BASE % B32 || IOS_SC2_E_BASE % B32) FAIL("PartitionAlloc blocks not on 32 GB boundaries\n");
        if (IOS_SC2_E_BASE != IOS_SC2_L_BASE + B32) FAIL("blocks not adjacent\n");
        if (IOS_SC2_FLOOR != IOS_SC2_L_BASE + IOS_SC2_POOL_REAL) FAIL("floor not above libcef's 4 GB\n");
        if (IOS_SC2_FLOOR >= 0x73ffff0000ull) FAIL("no furniture window\n");
        if (IOS_SC2_J2_BASE != IOS_SC2_L_BASE + 16 * GB || IOS_SC2_J2_BASE + IOS_SC2_MD_REAL != IOS_SC2_J2L_BASE
            || IOS_SC2_J2L_BASE + IOS_SC2_MD_REAL != IOS_SC2_E_BASE)
            FAIL("the metadata regions do not split libcef's BRP half\n");
        if (IOS_SC2_MD_ASK != 16 * GB || IOS_SC2_MD_REAL < IOS_SC2_POOL_REAL || IOS_SC2_MD_REAL < 8 * GB
            || IOS_SC2_J2_BASE % 0x10000 || IOS_SC2_J2L_BASE % 0x10000)
            FAIL("a metadata region does not cover its pools' real 4 GB and an 8 GB configurable pool\n");
        if (IOS_SC2_RW_ALIAS < IOS_SC2_E_BASE + IOS_SC2_POOL_REAL) FAIL("alias inside chrome_elf's 4 GB\n");
        if (IOS_SC2_RW_ALIAS + IOS_SC2_RW_MAX > IOS_SC2_CAGE_BASE) FAIL("alias into the cage\n");
        if (IOS_SC2_CAGE_BASE % (4 * GB) || IOS_SC2_CAGE_BASE + 8 * GB > IOS_SC2_OILPAN_BASE) FAIL("cage\n");
        if (IOS_SC2_OILPAN_BASE != IOS_SC2_E_BASE + 16 * GB) FAIL("Oilpan not at chrome_elf's block + 16 GB\n");
        if (IOS_SC2_OILPAN_BASE != IOS_SC_BRP_HOLD_BASE || IOS_SC2_OILPAN_BASE + IOS_SC2_OILPAN_SIZE != IOS_SC_ARENA_BASE)
            FAIL("Oilpan does not end at the FEX arena\n");
        if (IOS_SC_ARENA_BASE + IOS_SC_ARENA_SIZE != top) FAIL("arena does not end at 0x8000000000\n");
        printf("PASS: layout 2: 0x%llx libcef PA 4G | floor 0x%llx | 0x%llx chrome_elf metadata 8G | 0x%llx libcef "
               "metadata 8G | 0x%llx chrome_elf PA 4G | alias 0x%llx | cage 0x%llx | Oilpan 0x%llx | arena 0x%llx-0x%llx\n",
               IOS_SC2_L_BASE, IOS_SC2_FLOOR, IOS_SC2_J2_BASE, IOS_SC2_J2L_BASE, IOS_SC2_E_BASE, IOS_SC2_RW_ALIAS,
               IOS_SC2_CAGE_BASE, IOS_SC2_OILPAN_BASE, IOS_SC_ARENA_BASE, top);
    }

    /* commits of the helper, against its build-340 grants (cage: kind 9) */
    {
        struct ios_sc2_gv g[] = {
            { IOS_SC2_E_BASE, IOS_SC2_POOL_REAL, IOS_SC2_E_BASE, 32 * GB, IOS_SC2_E },
            { IOS_SC2_J2_BASE, IOS_SC2_MD_REAL, IOS_SC2_J2_BASE, 16 * GB, IOS_SC2_J2 },
            { IOS_SC2_L_BASE, IOS_SC2_POOL_REAL, IOS_SC2_L_BASE, 32 * GB, IOS_SC2_L },
            { IOS_SC2_J2L_BASE, IOS_SC2_MD_REAL, IOS_SC2_J2L_BASE, 16 * GB, IOS_SC2_J2L },
            { IOS_SC2_CAGE_BASE, 8 * GB, IOS_SC2_CAGE_BASE, 8 * GB, 9 },
            { IOS_SC2_OILPAN_BASE, IOS_SC2_OILPAN_SIZE, IOS_SC2_E_BASE, 32 * GB, IOS_SC2_OILPAN },
        };
        const int n = sizeof(g) / sizeof(g[0]);
        static const struct { uint64_t a, size; int c, kind; uint64_t off; const char *what; } cases[] = {
            { 0x73fffd0000ull, 0x20000, IOS_SC2_C_OK, -1, 0, "boot false alarm: a furniture commit" },
            { 0x7000004000ull, 0x10000, IOS_SC2_C_OK, -1, 0, "libcef's first slot span" },
            { 0x70f0000000ull, 0x10000, IOS_SC2_C_NEAR, IOS_SC2_L, 0x70f0010000ull, "libcef's pool near its end" },
            { 0x78f8000000ull, 0x4000, IOS_SC2_C_NEAR, IOS_SC2_E, 0x78f8004000ull, "chrome_elf's pool near its end" },
            { 0x7400001000ull, 0x1000, IOS_SC2_C_OK, -1, 0, "chrome_elf's metadata, super page 0 (build 340)" },
            { 0x7600201000ull, 0x1000, IOS_SC2_C_OK, -1, 0, "libcef's metadata, super page 1" },
            { 0x7600000000ull + 0xf0000000ull + 0x1000, 0x1000, IOS_SC2_C_NEAR, IOS_SC2_J2L, 0xf0000000ull,
              "libcef's super page at 3.75 GB" },
            { 0x7600000000ull + 0x100200000ull + 0x1000, 0x1000, IOS_SC2_C_PAST, IOS_SC2_J2L, 0x100200000ull,
              "libcef's super page past 4 GB" },
            { 0x7400000000ull + 0x100000000ull + 0x1000, 0x1000, IOS_SC2_C_PAST, IOS_SC2_J2, 0x100000000ull,
              "chrome_elf's super page past 4 GB" },
            { 0x7400403000ull, 0x1000, IOS_SC2_C_BRP, IOS_SC2_J2, 0x400000, "chrome_elf's BRP super page" },
            { 0x7600000000ull + 0x180000000ull + 0x5000, 0x1000, IOS_SC2_C_OK, -1, 0, "libcef's configurable pool at 6 GB" },
            { 0x7600004000ull, 0x4000, IOS_SC2_C_OK, -1, 0, "not a metadata page" },
            { 0x7900100000ull, 0x4000, IOS_SC2_C_BEYOND, IOS_SC2_E, 0x100100000ull, "the RW alias gap" },
            { 0x7a00010000ull, 0x4000, IOS_SC2_C_OK, -1, 0, "the V8 cage" },
            { 0x7c00100000ull, 0x4000, IOS_SC2_C_OK, -1, 0, "Oilpan" },
            { 0x7d00010000ull, 0x4000, IOS_SC2_C_OK, -1, 0, "the FEX arena" },
        };
        unsigned i;
        for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++)
        {
            int gi = -1;
            uint64_t off = 0;
            int c = ios_sc2_commit_class( cases[i].a, cases[i].size, g, n, &gi, &off );
            if (c != cases[i].c) FAIL("%s: class %d, not %d\n", cases[i].what, c, cases[i].c);
            if (c != IOS_SC2_C_OK && (g[gi].kind != cases[i].kind || off != cases[i].off))
                FAIL("%s: grant kind %d off 0x%llx\n", cases[i].what, g[gi].kind, (unsigned long long)off);
        }
        {   /* before libcef's metadata is given, its range is chrome_elf's unreserved half */
            int gi = -1;
            uint64_t off = 0;
            if (ios_sc2_commit_class( 0x7600001000ull, 0x1000, g, 3, &gi, &off ) != IOS_SC2_C_BEYOND
                || g[gi].kind != IOS_SC2_J2 || off != 0x200001000ull)
                FAIL("a commit in chrome_elf's unreserved metadata half\n");
            if (ios_sc2_commit_class( 0x7000004000ull, 0x4000, g, 0, &gi, &off ) != IOS_SC2_C_OK)
                FAIL("no grants\n");
        }
        printf("PASS: commits: furniture / arena / cage / Oilpan quiet; metadata pages flag a super page near or past "
               "a pool's real 4 GB or in the BRP pool; the unreserved part of a grant is reported\n");
    }
    return 0;
}
'''

with tempfile.TemporaryDirectory() as t:
    c = Path(t) / 'sclayout.c'
    c.write_text(harness)
    exe = Path(t) / 'sclayout'
    subprocess.run(['cc', '-std=gnu11', '-O1', '-Wall', '-Wno-unused-function', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', str(c), '-o', str(exe)], check=True)
    out = subprocess.run([str(exe)], capture_output=True, text=True)
    print(out.stdout, end='')
    assert out.returncode == 0, out.stderr
