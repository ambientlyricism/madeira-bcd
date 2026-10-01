#!/usr/bin/env python3
"""Ghost of Tsushima smoke-square diagnostics (docs/got-corruption.md); no device.

madeira-d3d12/src/pe/madeira_d3d12.c gained four switches, all OFF unless set
in madeira.cfg or the game's file: skip-ps (+ skip-ps-cycle), dxil-dump,
dxil-tess-patch-topology, and converter (DXIL) draws in the capture-ps walker.
This test

  * checks statically that every switch is read with a default that changes
    nothing, that the draw hook is behind its "unset" fast path, that the patch
    topology value reaches the converter service and both shader caches, and
    that capture-cs still logs under its own tag after the walker was shared;
  * cuts the skip-ps / dxil-dump functions out of the source, compiles them on
    the host with small stubs for the Windows calls and runs them: unset means
    nothing matches; a list matches exact pixel OR vertex entry names only;
    skip-ps-cycle rotates "nothing", first, second, ... with the clock; the
    dxil-dump list matches exact names.

SKIP (exit 0) when no host C compiler is found (cc, gcc or clang).
"""
import pathlib, re, shutil, subprocess, sys, tempfile

R = pathlib.Path(__file__).resolve().parents[2]
SRC = (R / "madeira-d3d12/src/pe/madeira_d3d12.c").read_text()
ABI = (R / "madeira-d3d12/src/madeira_ir_abi.h").read_text()
UNIX = (R / "madeira-d3d12/src/unix/madeira_ir_unix.mm").read_text()
CACHE = (R / "madeira-d3d12/src/unix/madeira_dxil_cache.h").read_text()
ok = True


def check(what, cond):
    global ok
    print(("ok   " if cond else "FAIL ") + what)
    ok = ok and bool(cond)


# --- static checks ---------------------------------------------------------
check("skip-ps read as a string (unset = no names)", 'mad_cfg_str_pe("skip-ps", buf, sizeof buf)' in SRC)
check("skip-ps-cycle defaults to 0", 'mad_cfg_int_pe("skip-ps-cycle", 0)' in SRC)
check("dxil-dump read as a string (unset = nothing dumped)", 'mad_cfg_str_pe("dxil-dump", g_dxil_dump, sizeof g_dxil_dump)' in SRC)
check("dxil-tess-patch-topology defaults to 0", 'mad_cfg_int_pe("dxil-tess-patch-topology", 0)' in SRC)
check("draw hook behind the skip-ps fast path",
      "if (g_skip_ps_state && mad_skip_ps_match(e->pso)) { MAD_SKIP(e); return; }" in SRC)
check("draw hook after the render pass began (clears still run)",
      SRC.index("if (g_skip_ps_state && mad_skip_ps_match(e->pso))") >
      SRC.index("if (!exec_begin_render(e)) { MAD_SKIP(e); return; }\n    if (g_skip_ps_state"))
check("dxil-dump hooks behind their fast path",
      SRC.count("if (g_dxil_dump_state && ") == 2)
check("the three tessellation stages ask mad_dtess_topology",
      len(re.findall(r"o[vhd]\.topology = mad_dtess_topology\(\(UINT\)desc->PrimitiveTopologyType\);", SRC)) == 3)
check("only the PATCH topology type is changed, and only when switched on",
      "return on && topo == (UINT)D3D12_PRIMITIVE_TOPOLOGY_TYPE_PATCH ? MADEIRA_IR_TOPOLOGY_PATCH_STRICT : topo;" in SRC)
check("the geometry-shader path keeps the plain topology",
      "ov.topology = (UINT)desc->PrimitiveTopologyType; ov.layout = L->n ? L : NULL;" in SRC)
check("ABI value defined", re.search(r"#define MADEIRA_IR_TOPOLOGY_PATCH_STRICT 0x104u", ABI) is not None)
check("service maps it to IRInputTopologyPatch (4)",
      "a->input_topology == MADEIRA_IR_TOPOLOGY_PATCH_STRICT) topo = (IRInputTopology)4;" in UNIX)
check("PE shader cache keys on input_topology", "mad_sc_feed_u64(&h, ((UINT64)a->gs_emulation << 32) | a->input_topology);" in SRC)
check("unix DXIL cache keys on input_topology", "mad_dxc_hu32(&s, a->input_topology);" in CACHE)
check("capture-cs keeps its log tag through the shared walker",
      'mad_capture_rs_tables(e, benc, seq, rs, e->croot, (const UINT32 (*)[64])e->cconsts, "capture-cs");' in SRC)
check("capture-ps walks a converter pipeline's root signature",
      'mad_capture_rs_tables(e, benc, seq, e->rs, e->root, (const UINT32 (*)[64])e->consts, "capture-draw");' in SRC)
check("GPU fault shaders still logged through the shared base64 writer",
      "mad_log_b64(hash, bc, len);" in SRC and 'GPU fault shader %016llx: end of bytecode' in SRC)
check("capture-ps matches exact names (no substring: ps_SetColor is not ps_SetColor_MultiLight)",
      "mad_name_in_list(g_capture_ps, e->pso->ps_name)" in SRC and "strstr(g_capture_ps" not in SRC)

# --- run the parsers on the host --------------------------------------------
cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
if not cc:
    print("SKIP: no host C compiler for the runtime part")
    sys.exit(0 if ok else 1)


def cut(sig):
    i = SRC.index(sig)
    j = SRC.index("{", i)
    depth = 0
    for k in range(j, len(SRC)):
        if SRC[k] == "{":
            depth += 1
        elif SRC[k] == "}":
            depth -= 1
            if depth == 0:
                return SRC[i:k + 1]
    raise SystemExit("unbalanced " + sig)


def line(prefix):
    m = re.search(r"^" + re.escape(prefix) + r".*$", SRC, re.M)
    if not m:
        raise SystemExit("missing global " + prefix)
    return m.group(0)


STUBS = r'''
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef long LONG; typedef long long LONG64; typedef unsigned long long ULONGLONG, UINT64; typedef unsigned UINT;
typedef size_t SIZE_T;
typedef struct { int unused; } SRWLOCK;
#define SRWLOCK_INIT { 0 }
static void AcquireSRWLockExclusive(SRWLOCK *l) { (void)l; }
static void ReleaseSRWLockExclusive(SRWLOCK *l) { (void)l; }
static ULONGLONG g_now_ms = 1000;
static ULONGLONG GetTickCount64(void) { return g_now_ms; }
static LONG InterlockedExchange(volatile LONG *p, LONG v) { LONG o = *p; *p = v; return o; }
static LONG InterlockedIncrement(volatile LONG *p) { return ++*p; }
#define MemoryBarrier() ((void)0)
static volatile LONG64 g_presents_now;
static char g_cfg_skip[512], g_cfg_dump[512]; static long long g_cfg_cycle;
static int mad_cfg_str_pe(const char *key, char *out, size_t cap) {
    const char *v = !strcmp(key, "skip-ps") ? g_cfg_skip : !strcmp(key, "dxil-dump") ? g_cfg_dump : "";
    snprintf(out, cap, "%s", v); return v[0] != 0;
}
static long long mad_cfg_int_pe(const char *key, long long dflt) { return !strcmp(key, "skip-ps-cycle") && g_cfg_cycle ? g_cfg_cycle : dflt; }
static int g_logs;
static void d3d12_log(const char *fmt, ...) { va_list ap; va_start(ap, fmt); g_logs++; vfprintf(stdout, fmt, ap); va_end(ap); }
struct mad_pso { char vs_name[64]; char ps_name[64]; };
'''

HARNESS = r'''
static struct mad_pso P(const char *vs, const char *ps) { struct mad_pso p; memset(&p, 0, sizeof p); snprintf(p.vs_name, 64, "%s", vs); snprintf(p.ps_name, 64, "%s", ps); return p; }
static void reset(const char *skip, long long cycle, const char *dump) {
    snprintf(g_cfg_skip, sizeof g_cfg_skip, "%s", skip); g_cfg_cycle = cycle; snprintf(g_cfg_dump, sizeof g_cfg_dump, "%s", dump);
    g_skip_ps_state = -1; g_skip_ps_n = 0; g_skip_ps_cycle = 0; g_skip_ps_phase = -1; g_skip_ps_dropped = 0; g_now_ms = 1000;
    g_dxil_dump_state = -1;
}
#define T(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); return 1; } } while (0)
int main(void) {
    struct mad_pso ml = P("ls_SetColor", "ps_SetColor_MultiLight"), ca = P("vs_SetColorCombinedAlpha", "ps_SetColorCombinedAlpha"),
                   sc = P("vs_SetColor", "ps_SetColor"), other = P("vs_Main", "ps_Deferred");
    /* unset: nothing matches, nothing logged, state settles to 0 */
    reset("", 0, ""); g_logs = 0;
    T(!mad_skip_ps_match(&ml) && !mad_skip_ps_match(&other)); T(g_skip_ps_state == 0); T(g_logs == 0);
    T(!mad_dxil_dump_wanted("ls_SetColor")); T(g_dxil_dump_state == 0);
    /* static list: exact pixel or vertex names, never a prefix */
    reset(" ps_SetColor_MultiLight, vs_SetColorCombinedAlpha ;", 0, "");
    T(mad_skip_ps_match(&ml)); T(mad_skip_ps_match(&ca)); T(!mad_skip_ps_match(&sc)); T(!mad_skip_ps_match(&other));
    T(g_skip_ps_n == 2);
    /* cycle 8 s over three names: 0-8 nothing, 8-16 first, 16-24 second, 24-32 third, 32 nothing again */
    reset("ps_SetColor_MultiLight,ps_SetColorCombinedAlpha,ps_SetColor", 8, "");
    T(!mad_skip_ps_match(&ml) && !mad_skip_ps_match(&ca) && !mad_skip_ps_match(&sc));
    g_now_ms = 1000 + 8000;  T(mad_skip_ps_match(&ml) && !mad_skip_ps_match(&ca) && !mad_skip_ps_match(&sc)); T(g_skip_ps_phase == 1);
    g_now_ms = 1000 + 16500; T(!mad_skip_ps_match(&ml) && mad_skip_ps_match(&ca) && !mad_skip_ps_match(&sc)); T(g_skip_ps_phase == 2);
    g_now_ms = 1000 + 24000; T(!mad_skip_ps_match(&ml) && !mad_skip_ps_match(&ca) && mad_skip_ps_match(&sc)); T(g_skip_ps_phase == 3);
    g_now_ms = 1000 + 32000; T(!mad_skip_ps_match(&ml) && !mad_skip_ps_match(&ca) && !mad_skip_ps_match(&sc)); T(g_skip_ps_phase == 0);
    T(!mad_skip_ps_match(&other));
    /* dxil-dump: exact names only */
    reset("", 0, "ls_SetColor, ps_SetColorCombinedAlpha");
    T(mad_dxil_dump_wanted("ls_SetColor")); T(mad_dxil_dump_wanted("ps_SetColorCombinedAlpha"));
    T(!mad_dxil_dump_wanted("ls_SetColo")); T(!mad_dxil_dump_wanted("ps_SetColor")); T(!mad_dxil_dump_wanted(""));
    /* the shared list matcher (capture-ps uses it too) */
    T(mad_name_in_list("ps_SetColor_MultiLight,ps_SetColorCombinedAlpha", "ps_SetColorCombinedAlpha"));
    T(!mad_name_in_list("ps_SetColor_MultiLight,ps_SetColorCombinedAlpha", "ps_SetColor"));
    T(mad_name_in_list(" a ;b\tc,", "c")); T(!mad_name_in_list("abc", "")); T(!mad_name_in_list("", "abc"));
    printf("harness ok\n");
    return 0;
}
'''

code = STUBS
for pfx in ("static char g_skip_ps_tok", "static volatile LONG g_skip_ps_phase", "static SRWLOCK g_skip_ps_lock",
            "static char g_dxil_dump[512]"):
    code += line(pfx) + "\n"
code += "\n" + cut("static int mad_name_in_list(const char *list, const char *name)") + "\n"
code += "\n" + cut("static void mad_skip_ps_load(void)") + "\n"
code += cut("static int mad_skip_ps_match(const struct mad_pso *p)") + "\n"
code += cut("static int mad_dxil_dump_wanted(const char *name)") + "\n"
code += HARNESS
with tempfile.TemporaryDirectory() as t:
    c = pathlib.Path(t) / "h.c"
    c.write_text(code)
    exe = pathlib.Path(t) / "h"
    p = subprocess.run([cc, "-std=c99", "-Wall", "-Wno-unused-function", "-Wno-unused-variable", "-o", str(exe), str(c)],
                       capture_output=True, text=True)
    check("harness compiles", p.returncode == 0)
    if p.returncode:
        print(p.stderr[-3000:])
    else:
        r = subprocess.run([str(exe)], capture_output=True, text=True)
        check("skip-ps / skip-ps-cycle / dxil-dump behave (" + r.stdout.strip().splitlines()[-1] + ")",
              r.returncode == 0 and "harness ok" in r.stdout)
        if r.returncode:
            print(r.stdout[-3000:])

print("PASS" if ok else "FAILED")
sys.exit(0 if ok else 1)
