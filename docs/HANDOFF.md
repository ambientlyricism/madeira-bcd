# Handoff: state of the madeira-bcd fork (2026-09-27)

> **Türkçe özet:** Bu dosya, Claude ile bu depoda yapılan bütün işin devir
> notudur; başka bir asistan (ör. ChatGPT Codex) buradan devam edebilsin diye
> yazıldı. Kullanıcıya Türkçe yanıt verilir. Teknik ayrıntıların tamamı
> `docs/madeira-bcd.md` içinde; bu dosya "nerede kaldık, kurallar neler,
> sırada ne var" sorularını cevaplar.

This file is for whoever continues the work (another coding agent or a
person). Read it first, then `docs/madeira-bcd.md` (every change this fork
makes, with the reason and the evidence), `docs/WOW64.md`, `docs/BUILDING.md`.

> **MANDATORY FOR EVERY AGENT (Claude, ChatGPT/Codex, anyone) -- owner's
> order, 2026-09-30.** The owner alternates between assistants. Every change,
> however small -- code, CI workflow, patch script, submodule pin, config
> default, build dispatched, device test result, owner decision, secret or
> account set up -- MUST be written into this file **in the same commit** (or
> the next one, before handing back to the owner): what changed, why, the
> evidence (log time / build number), and what is still open. Append; do not
> rewrite or delete earlier findings. If you only investigated and changed
> nothing, still note what you found. `AGENTS.md` and `CLAUDE.md` at the
> repository root repeat this rule. Start with section 0 (latest status).

## 0. Latest status (keep this section current; newest first)

* **2026-09-30 (Claude):** builds 244-252+ -- see "Builds 228-234" section for
  the full trail. In short:
  - 32-bit **Crysis** runs (D3D10 via DXMT, ~110 FPS unrecorded on build 249).
    Fixed: IAT sync, CPUID index, WOW64 TEB (x18), self-suspend (30 s gaps
    between intro videos), guest main thread QoS (it ran on E-cores only).
    **Open:** tree/branch geometry streaks in D3D10 (`-dx9` renders correctly
    but at ~28 FPS). Fixes in flight: zero-padded short constant buffers and
    realigned 16-bit index ranges -- the first versions skipped GpuManaged
    buffers and so never ran for static data; the build after 251 covers them
    and logs `[cb-short] ... encode:` / `[idx-align] ... encode:` counts.
  - **God of War** reaches the main menu; open issue is memory (jetsam at 8 GB).
    The owner is tired of regressions: before a risky change, keep the last
    good build as fallback. After the round-3 upstream merge fastsync is the
    default sync engine; God of War so far ran on madsync -- set its sync
    engine to Madsync in its game settings.
  - **Upstream round 3 merged** (100 commits, Steam library, fastsync default,
    FEX 26859e1 / wine 4f5b197 / dock 3cadfbe).
  - Build 254 (merge) failed on nsi_ndis/nsi_ip (HAVE_NET_ROUTE_H, fixed in
    the next build).
  - **OTA install** set up (section 2b). ECO toggle is in the in-game Session
    menu under "CPU" (LibraryHUD in Library.swift).
  - **Build 256 green** (run 36731040994, head 6e6f4c8, main fast-forwarded):
    merge + HAVE_NET_ROUTE_H fix + cb-short/idx-align with GpuManaged
    coverage. First OTA run worked: log 14:59:16 UTC notice "OTA: Madeira
    0.1.256 signed (profile expires 2027-01-27) ... kurulum-0.1.256.html
    written to the private bucket (links valid until 2026-10-07 14:59 UTC)".
    **Waiting on device test:** OTA install from kurulum-0.1.256.html,
    Crysis D3D10 trees (look for `[idx-align] ... encode: realigned` and
    `[cb-short] ... encode:` lines), ECO under Session -> CPU, God of War
    with Madsync (251 is the fallback).
  - **OTA install confirmed on device** (owner, 2026-09-30 18:27 UTC+3): the
    kurulum-0.1.256.html -> "Yükle" flow installed build 256 on the first try.
    The owner is now downloading 64-bit Crysis Remastered (19.4 GB) through the
    in-app Steam library. Note: 64-bit games use the committed PE d3d11.dll, so
    the cb-short/idx-align DXMT patches (i386 farm) do not apply to it.
    (Correction: pushing HANDOFF to main does not start a build -- build-ipa.yml
    runs on push only when the workflow file itself changes.)
    (Second correction: the first push of 6e6f4c8 to main DID start run 257,
    because main's previous head predates workflow changes that 6e6f4c8 carries;
    run 257 was a duplicate of 256 and is superseded by build 258.)
  - **Crysis Remastered (64-bit, Steam app 1715130) crash, log 2026-09-30
    18:42, build 256:** it reaches its window ("Crysis Remastered", 1024x768)
    and creates 23 DXMT D3D11 devices (FL 11_0), then its RenderThread (tid
    0108) calls RIP=0 with RCX = a stack pointer (`vkEnumerateInstanceVersion(&v)`
    shape; the host backtrace's first frame is vulkan-1.dll's base) ->
    c0000005 -> process exit; the later faults at 0x15a534000 /
    0x71f5771508 in xtajit64.dll are only fallout of the teardown (the JIT
    pool of the dead process was reclaimed while its threads ran). Cause: our
    vulkan-1.dll stand-in (tools/build-stub-dlls.py) returned NULL from
    vkGetInstanceProcAddr for everything, while the real Khronos loader always
    returns the global commands even with no driver. **Fix (build 258):** the
    stand-in now implements vkEnumerateInstanceVersion (1.3), empty instance
    extension/layer lists, vkCreateInstance -> VK_ERROR_INCOMPATIBLE_DRIVER,
    and vkGetInstanceProcAddr returns those five global commands (NULL for the
    rest), with real C prototypes so the arm64ec entry thunks pass arguments.
    Checked locally: the generated C compiles for arm64ec. Open: device test;
    if it still dies, look for the next NULL call in the same place.
  - **Build 258 green** (run 36739501697, head ab18526, main fast-forwarded):
    "vulkan-1.dll stand-in built (262 exports) and shipped"; OTA notice
    "Madeira 0.1.258 signed ... kurulum-0.1.258.html written to the private
    bucket (links valid until 2026-10-07 16:07 UTC)". Waiting on the owner's
    Crysis Remastered retry log.
  - **Owner, 2026-09-30 ~19:30 UTC+3, build 256:** 32-bit Crysis D3D10 tree
    streaks exactly as before -- the cb-short and idx-align fixes (now covering
    GpuManaged buffers) changed nothing visible (the log of that run has not
    been sent yet; ask for it to see whether their `encode:` counters fired).
    God of War: unchanged by the upstream merge, still dies of memory a
    little into play; the owner has not tried the memory swap setting yet.
  - **New lead for the tree streaks (build 259):** airconv's DXBC vertex fetch
    (dxbc_converter_basicblock.cpp) pulls attributes from base + stride*index
    with no bound, although the table entry carries the binding's length;
    the D3D9 path (dxso_compile.cpp, upstream) clamps to it -- and `-dx9`
    renders the trees correctly. D3D10 defines an out-of-range fetch as zero;
    Metal reads on. tools/patch-dxmt-vfetch-bounds.py (new, step "Patch DXMT
    vertex fetch bounds") routes a DXBC fetch at/past the length to the
    existing null-binding branch (zeros), logs `[vfetch-bounds] ... on` once,
    `MADEIRA_VFETCH_BOUNDS=0` turns it off, and bumps kDXMTShaderCacheVersion
    15 -> 16 so already-converted shaders are converted again (32-bit farm
    only; the committed 64-bit PE d3d11.dll keeps 15). airconv is native
    (dxmt-ios), so this reaches 64-bit D3D11 games too (see the correction
    below: God of War is D3D11; limited to SM 4.x shaders in build 260). Not compiled locally (no LLVM 15 headers here): CI is the check.
  - **OTA link by e-mail** (section 2b): owner asked for Google Drive instead of
    the B2 login; Drive cannot host an OTA install, so CI now e-mails the
    install page's pre-signed link when the OTA_MAIL_* secrets exist (added
    after build 259 was dispatched, so it rides the next build). Open: owner
    creates the app password and the three secrets.
  - **Log 2026-09-30 19:01 (named GoW.exe, build 256) is God of War, not the
    Crysis D3D10 run** (still missing): GoW reached the main menu on fastsync
    (inproc-sync unset -- Madsync was NOT selected) and idled there 18 min
    without dying. Memory at the menu: phys footprint ~7.7 GB (internal 4.1 GB
    + 2.35 GB compressed + 0.5 GB external), flat for the whole idle -- no
    leak at idle, but the menu alone sits just under the limit, so any
    gameplay allocation tips it over. DXMT census at the menu: METAL
    currentAllocatedSize 1.5 GB (tex-private 579 MB, buffers 793 MB), so most
    of the footprint is not GPU resources. **Correction:** God of War runs
    D3D11 through DXMT (mem-census), not D3D12 -- so the vertex-fetch-bounds
    change in airconv would have reached it. The patch now applies by default
    only to SM 4.x (D3D10-era) vertex shaders; GoW's SM 5.0 shaders convert
    exactly as before (MADEIRA_VFETCH_BOUNDS=1 all, =0 none). Build 259 (all
    shaders) was superseded by build 260 with this.
  - **Owner, 2026-09-30 evening:** will set up the Gmail app password and the
    OTA_MAIL_* secrets in the morning, and wants to "delete Backblaze from the
    workflow" once mail works. Told the owner: the e-mail only replaces the B2
    *login*; the IPA, manifest and signing files still live in the private B2
    bucket and the mailed link points there. Removing B2 needs another private
    store with expiring direct HTTPS links -- Google Cloud Storage (signed
    URLs; Google Cloud, not Drive) could replace it. **Owner's decision
    (2026-09-30 evening): keep Backblaze + the Gmail e-mail** (no migration);
    the owner adds the OTA_MAIL_* secrets in the morning from a PC. Do not
    remove B2.
  - **Crysis Remastered, log 2026-09-30 19:29, build 258:** the vulkan-1 fix
    worked -- the game starts, shows its menu, "New game" loads to 100 %, then
    dies. Before it: 15 x "DeviceTexture: Failed to register mach port for
    shared texture" (CreateTexture2D with a SHARED flag -> E_FAIL, because
    WMTBootstrapRegister/bootstrap_register2 is refused to an iOS app). Then
    RenderThread (tid 0110) reads address 0 in d3d11.dll rva 0x885ac =
    `MTLD3D11DeviceContextImplBase::ClearRenderTargetView` with a NULL view
    (the committed arm64ec d3d11.dll has symbols; `llvm-objdump -d` it). Level
    load memory: DXMT tex-private 4.5 GB, METAL currentAllocatedSize 1.9 GB.
    **Fix (next build):** tools/patch-winemetal-ios-shared-texture.py (native
    winemetal_unix.c, so it reaches the committed 64-bit PE too): on iOS a
    new shared texture gets no mach port, which DXMT's existing ml866 fallback
    turns into an unshared texture and S_OK. `[shared-tex]` logs the first 4;
    MADEIRA_SHARED_TEXTURE_PORT=1 restores the old path. God of War creates no
    shared textures (none in its 19:01 log). The null-RTV clear itself would
    still crash if it came from elsewhere (DXVK ignores a NULL view; DXMT's
    64-bit PE is a committed upstream binary, so that guard needs a PE rebuild).
  - Build 260 (5e90d18) was superseded early by build 261 (74ad830: vfetch
    bounds for SM 4.x + shared textures without mach port + OTA e-mail).
  - **Steam games' session logs (owner's request, 2026-09-30; not yet built --
    the owner said to hold it for the next build):** games started with the
    Steam licence (Madeira Dock: explorer.exe first, Valve's client picks the
    program) got no `Documents/logs/<exe>-<stamp>.txt`, because only the
    app's own launch paths call LogStore.startSessionLog. Now
    `madeira_steam_session_log` in build/ntdll-unix/process_ios.c
    (NtCreateUserProcess, after the spawn phase stamp) hard-links
    madeira-log.txt as `logs/<exe>-<local time>.txt` when a process under
    `steamapps\common\` starts (once per exe name; skips names containing
    fxc/redist/dxsetup/crash/setup/install -- Crysis Remastered spawns
    fxc.exe) and logs `[session-log] ... Steam game <exe>: logs/...`.
    Unit-tested on Linux in isolation (link made, fxc/duplicate/system exe
    skipped); ntdll-unix build on CI is the real check.
  - Owner asked (2026-09-30 night, B2 web keeps logging out) for the install
    links in chat until the mail is set up. Not possible by design: agents hold
    no B2 credentials (the key lives only in GitHub secrets; the one pasted in
    chat must not be used), and CI cannot hand the link over through the public
    Actions log. Pointed the owner to setting up the OTA_MAIL_* secrets from the
    phone (app password page + GitHub website in Safari) instead.
  - **Build 261 green** (run 36745357839, head 74ad830): all patch steps ran
    (vfetch bounds, winemetal shared textures), i386 farm rebuilt and saved,
    OTA notice "Madeira 0.1.261 signed ... kurulum-0.1.261.html ... valid until
    2026-10-07 17:04 UTC". Mail: "no OTA_MAIL_* secrets" -- the owner added
    them after the step ran. Build 262 (29c32ad: + Steam-game session logs)
    dispatched ~17:12 UTC as the first build with the secrets.
    (Correction to an earlier chat reply: 261 already contained the mail code;
    only the secrets were missing.)
  - **Build 262 green** (run 36749588085, head 29c32ad; main fast-forwarded,
    the duplicate push run 263 on main cancelled): Steam-game session logs,
    shared textures, vfetch bounds. **First e-mail went out**: log 17:29:06
    "OTA: install link for 0.1.262 e-mailed to the owner". Same log showed
    `aws: [ERROR] ... Unknown options: --only-show-errors` -- `aws s3 ls` does
    not take that flag, so the keep-the-last-10 cleanup silently never ran
    (builds 256-262 all still in the bucket). Fixed in sign-and-publish-ota.sh
    (plain `aws s3 ls --endpoint-url`); takes effect with the next build.
  - **Owner, build 262 (log CrysisRemastered.exe-2026-09-30_20-43-04.txt):** the
    mail arrived and worked; the Steam session log was named by exe (the new
    `[session-log]` line); `[shared-tex]` fired 4x and the game now gets past
    the load -- then dies "a few seconds later". Cause: JobSystem_Worker_0
    (tid 00a8) in kernelbase.dll rva 0x6d358 = **TlsGetValue** (`add x8, x18,
    w0, uxtw #3; ldr x0, [x8, #0x1480]`) with x18 == 0 (iOS zeroes x18):
    fault at 0x1570 (TLS slot 30). The mach handler's x18 emulation only
    handled Rn == 18 and printed `[x18-decline]`, so the AV killed the process
    (the xtajit64 faults after it are teardown fallout, as before). **Fix
    (next build):** `ios_x18_derived_base` in build/ntdll-unix/signal_arm64_ios.c
    -- when the instruction right before the fault is ADD (ext/shifted reg,
    imm) or MOV that wrote the faulting base register from x18, the fault
    address is the TEB offset and the existing TEB-relative emulation runs
    (logged `[x18-derived]`, first 8). Only a previously fatal path changes.
    Crysis Remastered memory at that point: footprint 4.8 GB.
  - **32-bit Crysis D3D10, build 262 (log Crysis.exe-2026-09-30_21-09-08.txt,
    2.5 min, no crash, footprint ~3 GB):** all three tree fixes fire --
    `[vfetch-bounds] ... on for SM 4.x vertex shaders` + bounded attributes,
    `[idx-align] ... encode: realigned`, `[cb-short] ... encode: zero-padded
    copy bound` (e.g. cb0 declared 80 vec4, bound 74). The owner has not yet
    said whether the trees still streak; asked. **Owner: unchanged, no
    improvement at all.**
  - **Build 264 green** (run 36755719496, head 88e1d6d, main fast-forwarded):
    x18-derived emulation; OTA mailed ("install link for 0.1.264 e-mailed"),
    the aws cleanup error is gone (8 builds in the bucket, nothing to delete).
  - **Next tree lead (build 265):** Crysis packs index data at 2-byte
    granularity; if its vertex buffers are bound at offsets/strides that are
    not multiples of 4, airconv's attribute loads (which claim natural
    alignment, 4 bytes for floats) read from rounded-down addresses on the
    GPU. tools/patch-dxmt-vb-align.py (new): SM 4.x vertex attribute pulls use
    alignment-1 loads (thread_local `madeira_vfetch_align1` set around the
    pull in pull_vertex_input, honoured in load_from_device_buffer;
    MADEIRA_VFETCH_ALIGN1=0 off, =1 all shaders; `[vfetch-align]` once);
    PE-side census `[vb-align]` of IASetVertexBuffers offsets/strides not
    4-aligned; shader cache version 16 -> 17. God of War (SM 5.0) unchanged.
    If `[vb-align]` stays silent, the theory is dead and this change is inert.
  - **Crysis Remastered, build 264 (log CrysisRemastered.exe-2026-09-30_21-19-06):**
    got further -- the owner saw the rendered scene for 5-6 s for the first
    time -- then the SAME TlsGetValue fault (pc pool+..358, addr 0x1570, x18=0,
    tid 00a8 "Main" this time) and `[x18-decline]`: the `[x18-derived]` path
    never fired, because the x18 patcher (virtual_ios.c, "via x18" form) had
    moved the `add x8, x18, w0, uxtw #3` into a trampoline (`mrs x18,
    TPIDRRO_EL0; and; ldr x18,[x18,#slot]; add; b back`), leaving `b tramp` at
    pc-4. TlsGetValue is hot enough that a preemption between the trampoline's
    ldr and its add (iOS zeroes x18) happens within seconds. **Fix (build 266):**
    ios_x18_derived_base follows a `b` at pc-4 when its target has exactly
    that trampoline shape and branches back to the fault, and checks the ADD
    inside it (unit-tested with the logged words: rn 8 -> derived, rn 9 -> not).
    Build 265 (vb-align) was superseded by 266 (vb-align + this).
  - **Build 266 green** (run 36758343731, head 72517a8; main fast-forwarded):
    i386 farm rebuilt with the [vb-align] census (725 files, exit 0, cached),
    all patch steps applied, OTA mailed ("install link for 0.1.266 e-mailed").
    Waiting on the owner: Crysis Remastered ([x18-derived]) and 32-bit Crysis
    D3D10 trees ([vfetch-align], [vb-align]).
  - **Crysis Remastered RUNS on build 266** (owner, 2026-09-30 ~22:12-22:35
    UTC+3, four logs, "harika çalışıyor"): `[x18-derived] ... base x8 from x18
    -> TEB+0x1490 emulated` fired 7x in the long run (6 min, no crash); none of
    the four logs has an access-violation exit. Open: **MetalFX upscaling did
    not engage** -- no MetalFX line in any log. Cause: a Steam game started
    with the Steam licence goes launchLibraryEntry -> startDock and returned
    before BCDLaunch.applyLibrary, so MADEIRA_CFG_GAME, DXMT_METALFX_SPATIAL_
    SWAPCHAIN / d3d11.metalSpatialUpscaleFactor, AVX, wine-vcrt and NVIDIA
    were never set for Steam games. **Fix (next build):** the Steam branch
    calls `BCDLaunch.applyLibrary(entry, sessionLog: false)` before startDock
    (the native side already names that session log after the exe); the
    `[bcd] library launch` line now also prints `metalfx=`. The committed
    64-bit d3d11.dll does contain DXMT's MetalFX spatial swapchain strings.
    Not compiled here (no Swift toolchain); CI is the check.
  - **Backblaze mail 2026-09-30 22:57 UTC+3: "Download Bandwidth Cap Reached
    75%"** of the free daily download allowance (1 GB/day on a free B2
    account). Every OTA install downloads the whole IPA (~150 MB) from the
    bucket; the owner installed about six builds today. Agents should have
    warned about this when the OTA was set up (not done). Facts for the owner:
    at 100% B2 blocks further downloads until the daily reset (00:00 UTC =
    03:00 UTC+3) -- with caps at the free level it does not charge; raising
    the cap (Caps & Alerts, needs a payment method) costs about $0.01/GB,
    i.e. ~0.15 cents per install. Longer term option: Cloudflare R2
    (S3-compatible, presigned URLs, no egress fees, 10 GB free storage) would
    need only endpoint/region/secret changes in sign-and-publish-ota.sh.
    Pending the owner's choice; nothing changed.
  - **Build 268 green** (run 36767022535, head 6e574ab, main fast-forwarded):
    Steam games get their game options. **Owner: MetalFX now works in Crysis
    Remastered.** Owner's decision: **move the OTA store to Cloudflare R2 in
    the morning** (2026-10-01). Prepared, not yet built: sign-and-publish-ota.sh
    uses R2 when R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY /
    R2_BUCKET all exist (endpoint <account>.r2.cloudflarestorage.com, region
    auto, same layout: Development.p12 + Development.mobileprovision at the
    bucket root, ota/ for builds, kurulum-<ver>.html at the root), else B2
    as before; logs `OTA: store R2|B2`. Owner's steps: create a private R2
    bucket, an R2 API token with Object Read & Write on that bucket only,
    upload the two signing files, add the four secrets. After the first R2
    build mails a working link, B2 secrets can be removed.
  - **Upstream sync 2026-10-01 (12h routine):** merged 40d5e74 "Library:
    ambient light around grid cards, a card press and a new not-installed
    look" (AmbientGlow/AmbientMovie behind grid cards, LibraryCardButtonStyle
    press, fainter not-installed cards; env.MADEIRA_LIBRARY_AMBIENT = 0 turns
    it off). One conflict in Library.swift: upstream's
    `.libraryCardButtonStyle(grid: !list)` kept together with our long-press
    context menu (Play / Game settings). ConfigCatalog regenerated (check
    PASS). No submodule changes. Build dispatched (it also carries the
    prepared, still inactive R2 support).
  - **Build 269 green** (run 36799153555, head 87830f1, main fast-forwarded),
    BUT its OTA step failed: `OTA: store B2`, signing fine, then `upload
    failed ... (InternalError) when calling the UploadPart operation (reached
    max retries: 2)` -- a transient B2 server error; no IPA, no mail. The
    main push started run 270 on the same commit; left running on purpose as
    the OTA retry. sign-and-publish-ota.sh now sets AWS_RETRY_MODE=adaptive,
    AWS_MAX_ATTEMPTS=10 (next build).
  - **Run 270 (push on main, same commit 87830f1) delivered the OTA:** "Madeira
    0.1.270 signed ... kurulum-0.1.270.html written to the private B2 bucket"
    and "install link for 0.1.270 e-mailed" (01:57 UTC). It also rebuilt the
    i386 farm (the farm cache is per branch, main had none for this key).
    GitHub glitch: run 270 still shows "in progress" (yellow) hours later
    although every step, incl. "Complete job", finished at 01:57 UTC; the
    cancel API answers 409 "not in progress". Nothing to fix on our side; the
    IPA, artifact and mail were all delivered.
  - **2026-10-01: upstream's author (Will Faust, Discord) asked the owner to
    contribute to upstream Madeira; the owner wants to.** Candidate upstream
    PRs (small, one topic each, each with its evidence): self-suspend in
    NtSuspendThread; guest main thread QoS attr (no fixed schedparam);
    wineserver priorities keep pthread QoS; x18-derived TEB emulation (incl.
    the patcher's trampolines); vulkan-1 stand-in global commands; iOS shared
    textures without mach port; Steam games get per-game options + session
    log by exe; DXMT short-cb / 16-bit index realign / SM4 vfetch bounds +
    byte-aligned fetch (the last three not yet proven to fix anything).
    Fork-only (not for upstream): OTA signing/mail, owner-specific secrets.
  - **OTA moved to Cloudflare R2 (2026-10-01).** The owner created a private
    R2 bucket and an Account API token (Object Read & Write, that bucket
    only), uploaded Development.p12 + Development.mobileprovision to the
    bucket root and added R2_ACCOUNT_ID / R2_ACCESS_KEY_ID /
    R2_SECRET_ACCESS_KEY / R2_BUCKET. **Build 271 green** (run 36831528440,
    head 8bfa683, dispatch; no code change since 270): notices "Madeira
    0.1.271 signed ... kurulum-0.1.271.html written to the private R2 bucket
    (links valid until 2026-10-08 07:53 UTC)" and "install link for 0.1.271
    e-mailed to the owner" (07:53 UTC). Open: owner to confirm the mailed
    link installs on the phone; then the B2_* secrets can be deleted (the
    script falls back to B2 only when an R2_* secret is missing) and the B2
    bucket emptied. Run 270 still shows "in progress" (GitHub glitch); it did
    not block 271's concurrency group.
  - **Owner confirmed (2026-10-01): the R2 mail arrived and build 271
    installed.** Owner's order: never exceed R2's 10 GB free storage, automate
    it. sign-and-publish-ota.sh now has a storage budget: the WHOLE bucket
    (signing files and anything else included) stays under OTA_BUDGET_GB
    (default 8 decimal GB, 2 GB headroom) and at most 10 builds; room for the
    new IPA is made BEFORE the upload (oldest builds first, the one being
    published never), and if even that is not enough (foreign files) the
    step fails with an ::error instead of uploading. A final check prints
    "OTA: bucket holds N builds, X GB of the 8 GB budget". Replaces the old
    keep-ten cleanup. Tested locally with a fake `aws` (listings of 12
    builds; with a 7 GB foreign file; tiny budget; re-publish of the same
    version). At ~150 MB per IPA, 10 builds are ~1.5 GB, so normally only
    the count rule removes anything. Build dispatched to verify on R2.
  - **Owner removed the B2_* secrets (2026-10-01).** Left: OTA_MAIL_* (3),
    R2_* (4), SIGN_P12_PASSWORD -- correct; with the R2 secrets the script
    never reads B2_*. (The workflow still passes the empty B2_* env; harmless.)
  - **God of War memory -- cause found (log GoW.exe 2026-10-01 11:03:41, build
    271, game settings swap-mb 6144 + swap-min-kb 1024 ["blocks"], global
    mempool 2048).** Died on a loading screen: footprint 5.1 -> 7.5 GB within
    11:04:15-11:04:17, then flat ~7.3 GB until the log ends at 11:05:07
    (pool reported memory pressure CRITICAL at 11:04:16; the last line is
    "keyboard focus: elsewhere (app inactive)", then nothing -- jetsam).
    Swap tier and pool worked (file-backed 2.1 GB, 0 refused; pool peak 530
    MB, then "guarded" as pressure rose) but cannot touch the growth: it was
    all native malloc -- `[malloc-zones]` DefaultMallocZone 489 MB / 0.89 M
    blocks (line 22126) -> 2887 MB / 2.93 M blocks (line 24411), ~1.2 KB per
    block; `[phys-map]` band "pa" 223 -> 2752 MB. During those seconds the
    busiest threads were the game's DxShaderCache0-3 (tids 00a0/00a4/00a8/
    00ac) -- it creates its shaders there; DXMT GPU memory stayed ~1.4 GB.
    DXMT's PipelineCache (d3d11_pipeline_cache.cpp) keeps every created shader
    forever (shaders_ map by SHA-1, never evicted) and each CachedSM50Shader
    holds airconv's parsed program from SM50Initialize (bbs of decoded
    instructions + signature_handlers std::functions), only needed while a
    variant is compiled. Fix (next build): tools/patch-airconv-sm50-lean.py
    (step "Patch airconv lean SM50 shaders", native only, not in the i386
    farm key): SM50Initialize still parses (reflection, argument and range
    info come from it), keeps a copy of the bytecode and drops bbs +
    signature_handlers; SM50Compile and the four tessellation/geometry
    pipeline entry points re-parse into a temporary for that call (parse is
    deterministic; compilation copies func_signature and only reads the
    shader). madeira-d3d12 uses only the public API, so it is covered too.
    MADEIRA_SM50_LEAN=0 restores the old behaviour; `[sm50-lean]` logs the
    mode and, every 1000 shaders, live count / bytecode kept / sampled bytes
    dropped per shader / malloc in use. airconv_cli sets LEAN=0 (it calls the
    internals directly). Not compiled locally (no LLVM 15 headers here); the
    patch chain applies cleanly and is idempotent on a scratch copy. Not yet
    proven: if `[sm50-lean]` shows little dropped per shader, the 2.4 GB is
    elsewhere (next suspect: compiled variants / Metal pipeline objects).
  - **Build 272 green** (run 36833812490, head cc83828, main fast-forwarded):
    storage budget verified on R2 -- "OTA: bucket holds 2 builds, 0.30 GB of
    the 8 GB budget", link mailed (08:18 UTC). Build 273 dispatched (run
    36835669781, head 914c951) with the lean SM50 patch. Owner keeps God of
    War's game config unchanged for the comparison (mipClampBC=2, WINEDEBUG
    err+all/err-virtual/fixme-all, swap-mb 6144, swap-min-kb 1024; global
    mempool 2048); 271 is the fallback.
  - **32-bit Crysis -dx9 now ~90 FPS on build 271** (owner, 2026-10-01; was
    ~28 FPS on 2026-09-30 before build 250). No log yet. Most likely cause:
    the guest main thread QoS fix (builds 250/251: it ran on E-cores only at
    2.1-2.6 GHz, [main-qos] class 0x21 now puts it on P-cores) plus
    fastsync as the default sync engine (round-3 merge). -dx9 renders the
    trees correctly, so it is a playable mode now; the D3D10 tree streaks
    stay open (271 carries vb-align/vfetch-align, not yet tested in D3D10).
  - **Build 273 green** (run 36835669781, head 914c951; main fast-forwarded to
    76a865f, the duplicate push run 274 cancelled): step "Patch airconv lean
    SM50 shaders" applied and dxmt-ios compiled with it; native ABI
    199d6904b41b587b; OTA "bucket holds 3 builds, 0.45 GB of the 8 GB
    budget", link mailed (08:39 UTC). **Waiting on device:** God of War with
    the same settings -- look for `[sm50-lean]` (mode line, then per-1000
    counts with KB dropped per shader and malloc in use) and compare
    `[malloc-zones]` with the 271 log (2887 MB after the loading jump).
  - **God of War FIXED past the loading screen on build 273** (owner,
    2026-10-01, ~09:00 UTC): playing, with **2.35 GB available memory**
    reported in game (271 died at ~7.5 GB footprint on the same loading
    screen with the same settings). The lean SM50 patch is the fix. Log not
    yet received; `[sm50-lean]` numbers (KB dropped per shader, malloc in
    use) to be recorded when it arrives. **273 is the new God of War
    baseline/fallback** (was 251/271). Upstream candidate: this is a strong
    one for Will (native airconv only, one file + a header field, env
    switch) -- add it to the candidate PR list above.
  - **Build 273 God of War logs 11:46:22 (1042x480) and 11:49:18 (1280x720),
    owner: "crashed when I raised the resolution".** `[sm50-lean]` numbers:
    25,000 shaders created and live, bytecode kept 480 MB (avg ~19 KB),
    sampled drop 27-33 KB per shader (noisy, 391 samples; early samples
    40-130 KB), malloc in use 876-894 MB; DefaultMallocZone 904-916 MB
    (271: 2887 MB). Footprint ~5.7-5.8 GB, peak 6.1 GB -- memory is fine now.
    Both crashes are the SAME, not memory: SEGV on DxRenderThread (0084) in
    ucrtbase.dll+0x62cc8 (byte copy, strb) writing to 0xffffffffffff0000,
    called from GoW 0x140b7e4e0 -- a buffered writer (dest = [buf+0x48] +
    [buf+0x38]) serialising MessagePack (bytes 0x82/0xd8): the game saving
    its settings after the change. Its buffer allocation had failed:
    hundreds of `[va-scan] FAILED ... gaps-exhausted` (210 in the second
    log), `errno=12 <-- STATUS_NO_MEMORY (callers see a NULL alloc)` -- the
    guest VA window 0x7000000000..0x73ffff0000 (16 GB) is exhausted, not
    RAM. Already present on 271 (227 va-scan FAILED), hidden by the jetsam.
    `[furniture]` at startup: 13.5 GB of the window mapped, the biggest
    items being the game's 1368 MB block and **the memory pool's 4 x 512 MB
    regions at 0x7027000000.. (2 GB of guest VA)**, of which only ~450-530 MB
    was ever used. Advice given: Memory pool Off (or 1 GB) for God of War --
    gives back up to 2 GB of guest address space; the lean SM50 fix already
    removed the memory pressure the pool was for. Open: confirm on device;
    longer term the pool should not live in the guest window (or should be
    sized to what the tier takes).
  - **Crysis 3 (32-bit, Bin32\Crysis3.exe, first try, build 271, log
    11:42:13).** Exits 0xc0000005 at 11:43:20 (~1 min). Cause: the 32-bit
    guest address space is full -- `[va-scan] FAILED window=0x7100110000..
    0x7200000000 size=0x410000 ... views=864 maxgap=0x400000`, `[alloc-fail]
    status=c0000017`, then winemetal refuses `MTLDevice_newBuffer from a
    32-bit caller with no caller-supplied memory (length 4194304)` and a
    write to 0x7100000000 (the 32-bit base, prot 0) kills it. DXMT itself
    held only ~220 MB (Metal 206 MB), footprint 3.5 GB: the game's own
    32-bit VA use fills the 4 GB. Advice: start Bin64\Crysis3.exe (64-bit,
    D3D11 via the committed d3d11.dll, no 4 GB wall). No crack lines seen
    in the parts read.
  - **God of War, build 273, Memory pool Off (log 11:56:52, 7 min, 1280x720,
    20 MB).** Furthest the owner has played. Pool off gave the guest window
    back its room: `[furniture]` at start free 7629 MB / biggest gap 7293 MB
    (pool on: 2804/2803 MB); `[va-scan] FAILED` 49 (210 before), no SEGV,
    no crash. Footprint peak 7.06 GB, 6.85 GB at the end (compressed 2.4 GB;
    swap tier file-backed 2.2 GB); video budget trimmed to 1246 MB at 6.9 GB.
    New symptom (owner): now and then the whole picture darkens slowly, "as
    if the sun sets", characters too, then a few seconds later it slowly
    comes back -- a smooth transition, not corruption. Reads like the game's
    auto-exposure (eye adaptation) being fed a wrong scene luminance. Facts:
    the game copies a texture to a staging resource ~once per frame
    (`[bc-stream] paths stg<-tex` 0 -> 11456 over the session, ~27/s) -- the
    usual CPU readback of the luminance/exposure value; no NaN/Inf or
    DO_NOT_WAIT lines exist to say more. Hypotheses, none proven: (1) a
    staging Map returning data the GPU copy has not written yet (zeros ->
    dark target -> smooth adaptation); (2) the luminance reduction itself
    (compute / mips) wrong on some frames; (3) real game behaviour. Note the
    64-bit d3d11.dll is upstream's committed binary (we cannot instrument
    Map there); native winemetal can log blits. Asked the owner: does it
    happen standing still with the camera fixed, and in which area.
  - **Another person's iPad, build 269, God of War (log 2026-10-01 10:39:48,
    40 MB, + screen recording 1:16), relayed by the owner: menu UI drawn,
    3D behind it black, after "select difficulty" all black, FPS 0-7, no
    crash.** The iPad has 7644 MB of RAM (hw.memsize) while the process
    limit reads 8192 MB, and the footprint sat at the limit: last
    `[footprint]` phys=8175 MB, compressed 4432 MB; HUD 7552-7958/8191 MB.
    Causes, all known: no game config (no mipClampBC -> tex-private 2.1 GB
    and climbing), build 269 has no lean SM50 fix (DefaultMallocZone 3066
    MB / 5.8 M blocks), MetalFX spatial 692x480 -> 1384x960 plus the frame
    interpolator on (HUD). The device is starved -- black frames, not a
    rendering bug. 3 SEGVs (0094/0098 at addr 0x3404, 0044 at 0) were
    handled; the game kept running. Advice: build 273+, God of War game
    config `dxmt = d3d11.mipClampBC=2`, `swap-mb = 6144`, `swap-min-kb =
    1024`, Memory pool Off, MetalFX and frame generation off; an 8 GB iPad
    has ~4 GB less headroom than the owner's 12 GB iPhone.
  - **Note for the owner (2026-10-01): the unsigned IPA is already
    downloadable** -- every build uploads `madeira-0.1.<run>-unsigned-ipa`
    as an Actions artifact, and on a public repository any signed-in GitHub
    user can download artifacts (default retention 90 days). That is how the
    iPad user got 269. Section 3 says not to publish IPAs (Microsoft
    redistributables, Apple's converter library inside) without the owner's
    decision; the artifacts are effectively such a publication. Put to the
    owner, not changed: (a) keep as is, (b) stop uploading the IPA artifact
    (the owner installs via OTA) or give it retention-days 1, (c) also put
    the unsigned IPA in the private R2 bucket and mail the owner a 7-day
    link he can pass to individual testers. Device-specific fix for the
    iPad: not needed before it is tested on 273 with the config above;
    if still starved, candidate: when hw.memsize < the jetsam limit (iPad
    7644 < 8192), base the reported RAM / video budget / trim thresholds on
    hw.memsize instead of the limit (virtual_ios.c ml992 only clamps the
    other way today).
  - **Owner's decision (2026-10-01): (a) -- unsigned IPA artifacts stay as
    they are** (downloadable from Actions). Do not change the artifact
    upload. Setup steps for the iPad user given to the owner to relay
    (Library long-press -> Game settings -> MetalFX/Frame generation Off,
    "Advanced: this game's config" lines, Settings -> Memory pool Off).
  - **RAM cap for 8 GB devices (owner's request 2026-10-01: optimise for 8 GB
    iPhones like 15 Pro / 16 Pro too, without touching what works now).**
    tools/patch-winemetal-ram-cap.py (step "Patch winemetal RAM cap for 8 GB
    devices", native winemetal only, not in the farm key): the video memory
    budget (ml1042 base, ml1075/ml1103 trim) and MadeiraCtl op 7 (headroom
    for DXMT's automatic BC mip clamp, also used by the committed 64-bit
    d3d11.dll) now plan with min(jetsam limit, hw.memsize - ram-reserve-mb);
    madeira.cfg `ram-reserve-mb` default 2048, 0 = off. `[ram-cap]` logs the
    cap once and once when it lowers something. Local stub test: iPad RAM
    7644 -> cap 5596 MB, limit 8192 -> 5596, headroom at 5000 MB footprint
    596 MB (was 3192); owner's iPhone RAM 11695 -> cap 9647 > 8192, every
    value unchanged. Not changed: the RAM Wine reports to games (ml992 --
    on the iPad it already reported hw.memsize because the 8192 measurement
    was rejected as larger than RAM).
  - **Owner (2026-10-01): delete the unsigned IPA artifacts of builds below
    260.** The GitHub MCP has no artifact delete, so a new workflow
    `.github/workflows/cleanup-artifacts.yml` (workflow_dispatch, input
    `below`, default 260; GITHUB_TOKEN with actions: write) lists every
    artifact page and deletes only `madeira-0.1.<N>-unsigned-ipa` with N <
    below; build-logs artifacts stay. Before: 370 artifacts, 29 old IPA ones
    on the first page alone (4.2 GB). It must be on main to be dispatched.
    Done: build 275 green first (run 36844076835, head e41139f, "Patch
    winemetal RAM cap" applied, native ABI 01e5d03be2878bbc, OTA mailed,
    bucket 4 builds 0.60 GB); main fast-forwarded to cd3b7dd, the duplicate
    push run 276 cancelled; cleanup run 36846074181: "deleted 64 IPA
    artifacts below build 260 (9.16 GB)".
  - **iPad (M1) on build 273: still black behind the menu, but no longer a
    memory problem** (screenshot relayed 2026-10-01: HUD "M1", 1280x720,
    App 5.72 GB, Available 2.87 GB, Metal 1.63 GB, 26.6 FPS; the menu UI and
    a film-grain noise are drawn, the 3D scene is black). So the 269 black
    was starvation plus something device-specific. Leading hypothesis (not
    proven, no 273 log yet): GPU family. M1 on iPadOS is Apple7 only (no
    Mac2); DXMT's own format table (dxmt/dxmt_format.cpp) gives R32Float /
    RG32Float / RGBA32Float the Filter capability only from Apple9 (A17
    Pro / M3 and later; the owner's A19 has it). A linear sampler on a 32-bit
    float texture on Apple7/8 is not supported by Metal -- typically reads
    back 0 -- and an exposure / luminance texture in R32F sampled bilinear
    would turn the lit scene black while UI and grain still draw. The
    owner's slow darkening may be a different thing (A19 can filter 32F).
    Would affect M1/M2 iPads and A14-A16 iPhones, not 8 GB A17 Pro/A18
    iPhones. Needed: the iPad's 275 log. Possible fix if confirmed: when the
    device cannot filter 32-bit floats (check MTLDevice
    supports32BitFloatFiltering as well as the family), make the sampler
    nearest for those formats or filter manually in the converted shader.
  - **Owner's decision (2026-10-01): drop the 32-bit Crysis games** (Crysis
    D3D10 tree streaks, Crysis 3 Bin32) -- "too old, not worth it". Focus is
    God of War. The SM4-only DXMT patches already in the build (cb-short,
    idx-align, vfetch-bounds, vb-align) stay: they do not touch SM 5.0
    shaders and cost nothing; do not spend more time on them. Open God of
    War items: the slow darkening (owner's question about camera/area
    pending), the iPad M1 black scene (275 log pending), upstream PR for
    the lean SM50 fix.
  - Upstream PRs wait (owner, 2026-10-01): he is not yet in the upstream
    Discord contributors channel; PRs will be requested there and the owner
    will say which ones. Do not open upstream PRs before that.
  - **God of War darkening, measured (owner's iPhone, build 275, log
    13:07:31 + 89 s recording made during minutes 2-3 of that log).** Frames
    every 0.5 s, mean brightness of the centre: ~20-40 normally, 28 -> 11
    between 33 and 38 s, ~10-12 until 74 s, back to ~30 by 88 s -- the whole
    picture, characters included, a smooth fade both ways. Owner: only
    outdoors, it started when stepping out of the house, never indoors -> the
    sky / sun drives it. Reads as auto-exposure fed a luminance that is far
    too high (or NaN/Inf). The log has no per-frame render values, so timing
    a new video to the log would not add anything. Two Metal-vs-D3D
    differences fit and are now switches (tools/patch-airconv-float-
    experiments.py, step "Patch airconv float experiments", all OFF by
    default): MADEIRA_PS_CLAMP=1 (finite pixel float outputs beyond +-65504
    written as +-65504, as D3D converts to float16 instead of overflowing to
    Inf), =2 (also Inf -> +-65504, NaN -> 0); MADEIRA_PRECISE_MINMAX=1
    (air.fmin/fmax, NaN-ignoring like D3D, instead of the fast variants --
    airconv's nt converter always used the fast ones). The native shader
    cache uses a separate table per combination (version + salt*1e6), so
    switching recompiles. Facts found on the way: airconv's UseFastMath sets
    contract/reassoc/reciprocal (PS and CS), approx-func and nsz, never
    nnan/ninf; CreateFPUnOp/BinOp default to air.fast_* variants.
  - **iPad M1, build 275 log (12:24:50).** RAM cap works: `[ram-cap] ... cap
    5596 MB`, video budget 1024 MB (process limit 5596), footprint 5.4 GB.
    The black scene stays. The log holds nothing about formats or filtering,
    so the same experiment build adds `[f32-tex]`: the device's
    supports32BitFloatFiltering + families 7/8/9 once, and the first sampled
    R32/RG32/RGBA32Float textures. The float switches above are worth trying
    there too (the black menu may be the same exposure collapse, permanent).
  - **Upstream released v0.1.0 (2026-10-01).** The tag points at upstream
    main 3ccbf9b "Library: liquid metal bar glass, Desktop button and app
    icon" (Will Faust, 2026-10-01 16:40 +0800) -- one commit after 40d5e74,
    the last one merged here; the 12h sync will bring it in. The release
    page / assets (how the IPA was built, its contents) could not be read
    from this session: the GitHub API and release pages of willfaust/madeira
    are blocked for unattached repos, and attaching it was denied by the
    permission classifier. Asked the owner how to proceed (paste the release
    text/asset list, or allow the access).
    Owner's way (2026-10-01): he uploads upstream's v0.1.0 IPA to a DRAFT
    release of this repo. New `.github/workflows/inspect-ipa.yml`
    (workflow_dispatch: tag, asset filter) downloads it with the job token,
    compares it with our newest unsigned IPA artifact and writes the job
    summary: Info.plist build keys (DTXcode, DTSDKBuild, BuildMachineOSBuild
    -> CI runner or a personal Mac), signature, LC_BUILD_VERSION, build paths
    found in the main binary (user names redacted), and the per-file
    difference of the two .app bundles. It never re-uploads an IPA and prints
    no URLs. Needs to be on main to be dispatched.
    Owner uploaded `Madeira-0.1.0.ipa` (136 MB) to an untagged draft
    ("madeira first release"); inspect-ipa now also matches a draft by name
    or by its untagged-... address. Release notes (pasted by the owner):
    ad-hoc signed IPA carrying the app's entitlements incl. the increased
    memory limit, sideloaded with the user's own Apple ID; iOS 17+, UI for
    iOS 26; contents of that build: liquid metal UI (MADEIRA_GLASS_SKIN=0 /
    MADEIRA_LIQUID_METAL=0), library ambient light / card press / icon-only
    tab bar, fastsync default, new icon -- nothing about RDR2 or other game
    fixes. **"The Microsoft Visual C++ runtime DLLs are not redistributed"**
    (legal/THIRD-PARTY-NOTICES.md, tools/fetch-vcruntime.md). Ours: CI step
    "vcruntime :: recovered 12 of 12" puts them into our IPA, and our unsigned
    IPA artifacts are downloadable by any GitHub user (owner chose to keep
    them, option (a)). Raised with the owner.
  - **Upstream v0.1.0 IPA inspected locally (2026-10-01).** The draft asset
    downloads through the session's proxy (our repo's API), sha256 29054bb5...
    as on the page. Findings: bundle id **com.willfaust.madeora** (ours keeps
    com.willfaust.mythicemu -> both can be installed side by side), version
    0.1.0 (1), MinimumOS 17.0; built with **Xcode 27.0 (27A266a), iPhoneOS
    27.0 SDK, on a Mac running macOS 26 (26A428)**, in the **Debug**
    configuration (Madeira.debug.dylib 57.5 MB + __preview.dylib next to a
    73 KB stub executable); 581 build paths `/Users/<user>/Documents/
    ios-pc-game-claude/...` and none from /Users/runner -> built in Xcode on
    Will's own Mac, not CI. x86_64-vcruntime/ is EMPTY (no Microsoft
    DLLs). d3d12/ ships Apple's libmetalirconverter.dylib with
    METAL-SHADER-CONVERTER-AGREEMENT.txt + NOTICE + header license, plus
    canary *.dxil; legal/ and licenses/ hold the notices. Content vs our
    tree: aarch64-windows 135/135 and arm64ec-windows 143/143 committed files
    byte-identical to ours (incl. the PE d3d11.dll); extra in the release are
    only build products (plugplay/svchost/winedevice.exe, dockhost.exe,
    dock-notices.txt). The native code's `mlNNNN` log tags in the release
    binary are all present in our source tree (ml506-508 are GDI blit logs);
    the highest is ml2015 on both sides -> **no unpublished fixes (RDR2 or
    otherwise) in the release; everything in it is in the repo, and our fork
    already has all of it but the UI commit 3ccbf9b.** inspect-ipa.yml stays
    on the branch (not needed for this one).
  - **Build 277 green** (run 36849823493, head 1563ac6): "Patch airconv
    float experiments" applied, native ABI e2565aa5b1737703, OTA mailed,
    bucket 5 builds 0.75 GB. Waiting on device: MADEIRA_PS_CLAMP=1/2 and
    MADEIRA_PRECISE_MINMAX=1 on the owner's iPhone (outdoor darkening) and the
    iPad (black scene, plus `[f32-tex]` lines).
  - Owner: the cleanup left IPA artifacts older than ~164. Those builds used
    the fixed name `madeira-unsigned-ipa` (83 artifacts). cleanup-artifacts
    now deletes that name too.
    Done: main fast-forwarded to 9607361 (duplicate push run 278
    cancelled), cleanup run 36851915094 "deleted 83 IPA artifacts ... (5.59
    GB)". IPA artifacts left: 261-273, 275, 277 (12); 227 artifacts in all.
  - Owner (2026-10-01), after learning upstream ships no VC++ DLLs: keep the
    unsigned IPA artifacts as they are (decision (a) confirmed). He will not
    try upstream's v0.1.0: it has nothing ours lacks except the liquid-metal
    UI, and lacks the lean SM50 fix God of War needs.
  - **Float experiments on the owner's iPhone, build 277 (logs 14:03:35
    PS_CLAMP=2, 14:06:00 PRECISE_MINMAX=1, 14:08:27 none, 14:12:49
    PS_CLAMP=1, 14:15:18 PRECISE_MINMAX=1): none of them stops the outdoor
    darkening.** The switches did apply (`[madeira-env] game ...`,
    `[ps-clamp] ... mode 1/2`, `[precise-minmax] ... precise`) and the salted
    cache made them recompile, so both theories are refuted on the A19.
    `[f32-tex]`: "Apple A19 Pro GPU: supports32BitFloatFiltering=1
    apple7=1 apple8=1 apple9=1"; GoW creates 12 sampled 32-bit float
    textures, among them **R32Float 128x64 with 8 mips and 64x32 with 7 mips
    -- a luminance pyramid down to 1x1** (auto-exposure), plus R32F
    1920x1080 / 1280x720 / 960x540 / 640x360 / 2048x1024 and RGBA32F 1024x1,
    240x135, 160x90. DXMT's GenerateMips is a Metal blit generateMipmaps on
    the SRV's view (d3d11_context_impl.cpp), which needs a filterable
    format -- fine on the A19, NOT on a device without 32-bit float
    filtering: strong candidate for the M1 iPad's black scene (its 277 log
    will say supports32BitFloatFiltering=0/1). Next iPhone test (no build):
    the only Madeira-specific texture change in the God of War config is
    `dxmt = d3d11.mipClampBC=2` (Madeira's ml670/ml675 clamp, not upstream
    DXMT): remove it, set the in-game texture quality to Low to keep memory
    in bounds, and go outdoors.
  - Owner: the darkening happens wherever the sky is in view (not in every
    open area). **mipClampBC removed (log 14:23:35, build 277): still
    darkens**, footprint up to 6.98 GB (owner: RAM rose for nothing) -> the
    clamp is not the cause; owner told to put the line back.
  - Next build: tools/patch-winemetal-lum-probe.py (step "Patch winemetal
    luminance probe", native, default ON, MADEIRA_LUM_PROBE=0 off).
    `[lum-readback]`: every texture->buffer copy of <= 4x4 texels from a
    32-bit float texture is remembered; at the next one the previous copy's
    CPU-visible destination is read and logged (throttled ~2/s: format,
    level, size, 4 floats). `[f32-mipgen]`: 32-bit float GenerateMips (fmt,
    size, levels). Goal: see the luminance value the game reads at the
    moment it darkens -- huge/Inf/NaN = the GPU computes it wrong; sane
    values = CPU side / readback timing. Not tested locally (no Metal here);
    patch applies cleanly and is idempotent on a scratch copy.
  - Owner asked (2026-10-01) for a "fit in 8 GB" demo video: told him the
    knobs (madeira.cfg `ram-reserve-mb = 6100` -> Madeira's budgets as on a
    7.6 GB device, `totalphys = 7644` -> the game sees 7.6 GB) but that a
    12 GB phone does not reproduce 8 GB jetsam/pressure, so such a video is
    not proof; the honest evidence is the M1 iPad log (footprint 5.4 GB, no
    crash). Nothing changed.
  - **Owner request: DirectInput / native DualSense.** Today GameController
    state goes into a 20-byte XInput-shaped snapshot (app/Madeira/Winios/
    WiniosGamepad.[ch], read by build/win32u-unix/driver_ios.c) that only
    xinput sees, so every pad is an Xbox pad and dinput/hid see nothing.
    winebus.sys is not built for iOS (its source has bus_sdl/iohid/udev
    backends; hid.dll, setupapi.dll, dinput(8).dll are shipped). Plan put to
    the owner: (1) build winebus.sys + a new iOS backend that creates a
    virtual HID device per GameController pad -- a real DualSense report
    layout (Sony VID 054C / PID 0CE6) for GCDualSenseGamepad so dinput8,
    raw input and Sony's own libScePad (God of War, Ghost of Tsushima) see a
    PS5 pad with PS prompts; generic HID gamepad for others; (2) output
    reports -> rumble, adaptive triggers, light bar via GCDualSense APIs;
    (3) touchpad and gyro. Needs the PnP path (winedevice/plugplay) to load
    winebus on device. Multi-day; not started.
    Owner's go (2026-10-01): XInput stays the default and unchanged; add a
    DirectInput/HID choice to the in-game session menu (LibraryHUD); he
    authorised a second agent so this does not block other work. Launched in
    its own git worktree: it researches first (CrossOver/winebus iohid+sdl,
    SDL's PS5 HID layout, GameController DualSense APIs), then phase 1
    (winebus on iOS + virtual DualSense 054C:0CE6 / generic HID pad + menu
    picker + per-game key), commits locally only (no push, no CI) and writes
    its notes into a subsection "DualSense / DirectInput (second agent)" at
    the end of section 0. The main session reviews, merges and builds.
    `.claude/worktrees/` (the agent's worktree) is now in .gitignore.
    The owner stopped that agent by accident; its uncommitted work (18 files,
    ~2200 lines: build/hidpad/*, build/wineserver/hidpad_ios.c, server_ios.c,
    WiniosGamepad, LibraryHUD picker, host test check-hidpad.py) was saved as
    local commit 7da53e7 on branch worktree-agent-ad222c1a2512434bd (not
    pushed, not built). A stopped agent cannot be resumed, so a new agent
    was started on the owner's go: it first reviews 7da53e7 critically,
    cherry-picks and finishes it if sound, otherwise starts over cleanly
    (owner: "no mistakes; start over if it gets messy"). Same rules (local
    commits only, notes in the "DualSense / DirectInput (second agent)"
    subsection).
  - **Build 279 green** (run 36855551967, head 4dea9ee): "Patch winemetal
    luminance probe" applied, native ABI d629033a90627b60, OTA mailed,
    bucket 6 builds 0.90 GB. Waiting on device: owner reproduces the
    outdoor darkening with the old config (mipClampBC=2 back, no MADEIRA_
    switches) and sends the log -> read `[lum-readback]` / `[f32-mipgen]`.
  - **Build 279 on device (log 14:51:20, darkest in the last ~10 s; owner:
    the darkness does not depend on the camera at all).** Probe on, but
    `[lum-readback]` 0 and `[f32-mipgen]` 0: the ~27/s texture->staging
    copies (stg<-tex 0 -> 3310 in 2 min) are not small 32-bit float
    textures, and the game never calls GenerateMips on its R32F pyramids
    (they are reduced by its own shaders). Footprint peak 6.3 GB. Next:
    tools/patch-winemetal-readback-census.py (step "Patch winemetal readback
    census", same MADEIRA_LUM_PROBE switch): `[rb-tex]` lists every new
    (format, size, level) of texture->buffer copies, top six every 1024th,
    and the values of the previous copy of <= 64 texels (~2/s, floats + hex);
    `[rb-buf]` the same for buffer->buffer copies of <= 256 bytes into shared
    buffers (first 8 floats). Applies cleanly after the lum probe on a
    scratch copy; Objective-C not compiled locally.
  - **Darkening gone at 1920x1080 (owner, build 279, log 15:01:54:
    display-shape 1920x1080 + MetalFX 2x -> 3840x2160; "completely
    gone").** MetalFX is not the factor: the 11:56 session had MetalFX 1.5
    (1280x720 -> 1920x1080) and darkened; 14:51 (1568x720, no MetalFX)
    darkened. What differs: GoW starts with a 1920x1080 set of render
    targets (R32F 1920x1080, 960x540, 60x34, RGBA32F 240x135, ...); at a
    720-line window it creates a SECOND set (R32F 1280x720, 640x360, 40x23,
    RGBA32F 160x90) -- `[f32-tex]` in 14:51 vs 15:01. At 1080p no second
    set is created and no darkening happens. So the bug follows the game's
    switch away from its 1920x1080 start-up size (a resize path: a stale
    1080p-sized resource or view still read after the switch is the likely
    shape; not proven). Workaround given: play God of War at display
    resolution 1920x1080 (MetalFX optional). Side finding while looking:
    DXMT's presenter scales HDR output by currentEDRHeadroom /
    potentialEDRHeadroom (dxmt_presenter.cpp), which would also dim the
    whole picture when iOS lowers the headroom -- only relevant if the game
    runs in HDR; no log evidence that it does.
  - **Confirmed (owner, log 15:06:44, build 279): native 1080p without
    MetalFX is fine; turning on FSR 2 Quality/Balanced (internal resolution
    below 1080p) made it darken at once.** `[f32-tex]` in that log: the
    1080p set, then RG32Float 1x1 x2 (FSR 2's exposure textures) and the
    720p set when FSR came on. Owner: Winlator+DXVK at 720p has no such
    darkening -> a DXMT/airconv difference. Cause found in airconv: DXBC `ld`
    and `ld_uav_typed` became a plain Metal read() with no range check
    (nt/dxbc_converter_base.cpp InstLoad / InstLoadUAVTyped); D3D returns 0
    out of range (DXVK via Vulkan robustness). GoW's 32x32 luminance tiles
    over 1280x720 are 40x22.5 -> 23 rows, so the last row reads rows
    720..735 past the bottom (at 1080p: 60x33.75 -> 34 rows, also past, but
    evidently harmless there -- not explained yet). Fix:
    tools/patch-airconv-ld-bounds.py (step "Patch airconv texture load
    bounds", after the float experiments): for 2D / 2D-array / 3D (incl.
    depth) textures, check mip < mip count, coordinate < size at that mip,
    slice < array length; read at a clamped address; select 0 when out of
    range. Default ON, MADEIRA_LD_BOUNDS=0 off, `[ld-bounds]` logs the mode;
    the native cache salt gets +100 when on, so the first launch reconverts
    every shader. Not compiled locally (no LLVM 15 here); patch chain
    applies cleanly and is idempotent on a scratch copy.
  - **Build 282 green** (run 36860447690, head 50a95fb; run 281 with the
    readback census alone was cancelled by it): "Patch airconv texture load
    bounds" and "Patch winemetal readback census" applied and compiled,
    native ABI 413d09f97f39c4c5, OTA mailed, bucket 8 builds 1.20 GB.
    Waiting on device: God of War at 720p (or FSR on at 1080p), outdoors --
    does the darkening stay away? `[ld-bounds] ... on` must be in the log;
    `[rb-tex]` / `[rb-buf]` show the readbacks.
  - **M1 iPad, build 277 (log 14:27:46, display 1280x720, PRECISE_MINMAX=1,
    still black).** `[f32-tex] ... Apple M1 GPU: supports32BitFloatFiltering=1
    apple7=1 apple8=0 apple9=0` -> the 32-bit float filtering theory is
    refuted. But the second render-target set there is **640x360** (R32F
    640x360, 320x180, 20x12; RGBA32F 80x45): GoW renders at a quarter of
    1280x720 on that device, and its 32x32 luminance tiles over 640x360 are
    20x11.25 -> 12 rows, so the last row reads 24 of its 32 texel rows past
    the bottom -- the same out-of-range `ld` as the iPhone's darkening, much
    larger. Very likely the same bug: dimmed on the iPhone at 720p, black at
    360p. The 282 fix (texture load bounds) should cover both; asked the
    owner to have the iPad user try 282. Footprint 5.6 GB, no crash.
  - **Build 282 on the owner's iPhone (log 15:52:42, 1280x720, `[ld-bounds]
    ... on`): darkening still there, ~20 % milder ("not pitch black
    anymore").** Readback census: the game reads back one 32x32 RGBA16Float
    texture every frame (fmt 115, ~27/s, too big for value dumps) and three
    small buffers: 16 B, 64 B (always zeros), 208 B. The **16-byte one is the
    exposure state** (x, e, z, w): outdoors x ~ -0.15, e (exposure factor)
    ~0.05-0.09, z ~1500; at start x=11.9/z=4384, menu/house x~2.26,
    e=0.0175, z~3120; e=0.2331 with w=0/1 looks like a reset/default. Every
    few tens of seconds ONE readback jumps to x=5..6, z=4000..5200 (15:53:53,
    15:54:25, 15:54:34, 15:55:46) and right after it e falls (0.086 ->
    0.028) and climbs back over seconds = the darkening. Single-frame spikes
    in an unchanged scene suggest memory corruption (or a stale read). Note:
    the probe reads the PREVIOUS small copy at the time of the next one, so a
    value can be stale if the GPU had not finished; the e drop after each
    spike is game state, though. Next fix: tools/patch-airconv-uav-store-
    bounds.py (step "Patch airconv typed UAV store bounds"): store_uav_typed
    on 2D/2D-array/3D textures branches around the Metal write() when out of
    range (D3D drops such writes); same switch MADEIRA_LD_BOUNDS; cache salt
    for "on" 100 -> 200. Texture atomics are not covered yet. DXMT already
    zero-initialises new textures (ResourceInitializer::initWithZero, used
    when pInitialData is NULL), so garbage-initialised targets were ruled out.
  - **Upstream sync 2026-10-01 13:00 UTC (12h routine): merged 9 commits up to
    69b2fc0** -- 3ccbf9b liquid-metal bar glass / Desktop button / app icon
    (= the v0.1.0 tag), e9cb4ed..03f3796 README rewrite (banner, Discord,
    iOS 26+, badges), ea25322 "Remove the early architecture study and the
    handoff notes" (ARCHITECTURE_ANALYSIS.md, STEAM_CEF_HANDOFF.md,
    research/HANDOFF-*.md, patches/*.patch, scripts/deploy-thumper.sh;
    none used by our CI), **79e28f0 "Reorganize the repository"**:
    research/dxmt -> dxmt, research/madeira-dock -> madeira-dock,
    research/madeira-d3d12 -> madeira-d3d12, build/host-tests -> tests/host,
    build/{x64,x86,dxmt,proc,net}-tests -> tests/*, scripts/* -> tools/*,
    research/madeira.cfg.example -> docs/; 69b2fc0 liquid-metal toggle in
    Settings (Liquid Glass default). Submodule pins unchanged (FEX 26859e1,
    wine 4f5b197, dxmt a5e0cd3, dock 3cadfbe), only paths. Our side: every
    path in our tools/*.py|sh (all patch-dxmt-*/patch-airconv-*/
    patch-winemetal-* scripts now use ROOT dxmt/src), build-ipa.yml,
    build-pack.yml, build/madeira-d3d12/madeira_ir_stub.c and
    docs/madeira-bcd.md rewritten to the new layout; our
    research/madeira-d3d12/src/pe/mad_kernels.metal moved with its directory;
    ConfigCatalog regenerated (tests/host/check-config-catalog.py PASS). The
    i386 farm cache key changes (build/wine-i386/build.sh changed upstream),
    so the next build rebuilds the farm. Local checkout: the dxmt submodule
    git dir moved to .git/modules/dxmt. **The second agent's branch is based
    on the old layout (build/host-tests/check-hidpad.py etc.): rebase its
    paths when merging it.** Older notes in this file keep the old paths.
  - Upstream's author on the DualSense plan (relayed 2026-10-01): "will the
    iPhone let you send haptics to the DualSense? macOS gives full USB access;
    iOS abstracts everything." Fair: iOS offers GCDualSenseGamepad state,
    GCDualSenseAdaptiveTrigger modes, GCDeviceLight, GCMotion and CoreHaptics
    via GCDeviceHaptics -- no raw HID, no USB, no audio-channel ("advanced")
    haptics, no speaker/mic. The goal stated back: PS prompts in Sony ports
    (libScePad sees a synthesized DualSense HID device) and a gamepad for
    DirectInput games = phase 1; output reports mapped best-effort (rumble ->
    CoreHaptics, trigger effects -> nearest adaptive-trigger mode, lightbar)
    = phase 2. The running agent was told the same scope.
  - **DualSense / HID pad merged (main session review, 2026-10-01).** The
    second agent finished phase 1 (its report and notes: subsection
    "DualSense / DirectInput (second agent)" below; docs/CONTROLLERS.md).
    Design kept from the stopped agent's WIP: the pad is a device served by
    the in-process iOS wineserver (build/wineserver/hidpad_ios.c, Wine's
    hidparse compiled in via build/hidpad/), not winebus.sys (no
    winedevice/plugplay on iOS, services disabled in the prefix); ntdll
    (server_ios.c) writes the Enum\HID registry keys level by level. Opt-in:
    `env.MADEIRA_PAD_MODE = hid` (game file / madeira.cfg) or Session menu
    > Controller; default XInput is untouched (beginPadSession only unsets
    MADEIRA_HIDPAD and logs `[hid-pad] ml2100 session mode=xinput`;
    madeira_hidpad_init returns at once without it). Reviewed by me: the
    XInput gating, the wineserver/ntdll entry points, the Swift
    (WINIOS_HIDPAD_* are unsigned literals -> UInt32 in Swift, buttons is
    UInt32; MadeiraConfig.gameValue and GamepadInput.optIn exist). Merge
    resolved the ConfigCatalog conflict by regenerating (check PASS);
    tests/host/check-hidpad.py PASS against the wine submodule; check-
    gamepad / library-sections / launch-routing / cfg-early-docs PASS. Swift
    and main_ios.c not compiled locally -> the next CI build is the first
    compile. Phase 2 (rumble/triggers/lightbar) and 3 (touch coords, gyro)
    not implemented.
  - **Build 284 green** (run 36865536001, head cd6039a, before the upstream
    and DualSense merges): "Patch airconv typed UAV store bounds" applied,
    native ABI 4bfb0dace1b73c83, OTA mailed, bucket 9 builds 1.35 GB. Owner
    tests the darkening on it (720p outdoors). Next: build 285 from a00148a
    = upstream reorganisation merge + layout fixes + DualSense HID pad (first
    CI compile of the pad's Swift / main_ios.c; i386 farm rebuild because
    build/wine-i386/build.sh changed upstream).
  - **Ghost of Tsushima: "No installed graphics card" again -- cause: a stale
    Apple adapter in the shared prefix (2026-10-01, logs GhostOfTsushima.exe
    16:15:35 and 16:16:49, build 282).** First GoT launch since 2026-09-28. Both
    launches stop at the dialog right after the game's probe device
    (D3D12CreateDevice -> destroyed Device -> dialog, presents=0). NOT a lost
    fix: `[vgpu] registered PCI\VEN_10DE&DEV_2544... driver 35.0.15.6094` is
    there, nvapi64.dll loads, DXGI reports 2544. What changed is the registry:
    every game shares one prefix and the in-process wineserver saves the
    registry, and since 2026-09-29 every God of War / Far Cry 5 / Crysis launch
    (NVIDIA reporting off) registered `PCI\VEN_106B&DEV_0001...` (Apple). So
    Enum\PCI held two display devices, both with Driver = Class\{display}\0000;
    the Apple one sorts first. On 2026-09-28 only GoT ran (all logs that day
    are 10de:2544 only) and it got past the check -- except 20:41:17, which
    shows the same "[NxApp] Failed to get GPU Driver Info" + dialog and stays
    unexplained (nothing else logged in between; maybe an unlogged launch).
    Fix (build/win32u-unix/sysparams_ios.c, `ios_forget_virtual_gpu`): before
    `ios_register_virtual_gpu` writes its adapter it deletes the OTHER
    identity's Enum\PCI device key and its two DeviceClasses links
    ({5B45201D...} display adapter, {1CA05180...} arrival); logs `[vgpu]
    removed the stale 106b:0001 adapter (N keys) ...`. Class\{display}\0000,
    Video\{guid}\0000 are shared and overwritten anyway; DirectX\{guid} is
    volatile. Helper checked in isolation (key names match link_device's);
    the full file is first compiled by CI. Workaround until the build is
    installed: none in the app (pressing Tamam continued the game on
    09-28 20:41). Waits for build 286 (285 is running the i386 farm; a new
    dispatch would cancel it). Note: the 282 log has no `[guest-log]` lines
    at all (09-28 had `ml1300 text-log support`), so the game's own text log
    is not mirrored any more. Its source is in neither this repo's history
    nor the wine / FEX submodules at their current pins, so it most likely
    left with the build 222 switch to upstream's pins. Low priority; it is
    what showed "[NxApp] Failed to get GPU Driver Info" on 09-28.
  - **Build 285 FAILED** (run 36867598003, head b449714, 2026-10-01 13:37
    UTC) in "Build dxmt-ios": `dxmt/src/winemetal/unix/winemetal_unix.c:2:
    fatal error: '../../../../../build/madeira_cfg.h' file not found`. Cause:
    upstream's reorganisation (79e28f0) moved research/dxmt to dxmt on the SAME
    dxmt pin a5e0cd3, whose winemetal unix sources count "../" from the old
    place: madeira_cfg.h (5 levels up was the root, now 4) and
    "../../../../remote-metal/..." in winemetal_unix.c, wmt_remote_client.h,
    wmt_remote_pack.h (4 levels up was research/, now the root; remote-metal
    stayed in research/). Upstream main has the same pin, so its tree has the
    same break. Fix: tools/patch-winemetal-layout.py rewrites those four
    includes (idempotent, tested twice on a copy; every new path resolves),
    run as the step "Patch winemetal includes for the new layout" before the
    other winemetal patches. Everything else in 285 passed up to there:
    ntdll 37/37, win32u, wineserver (with the HID pad's main_ios.c /
    hidpad_ios.c), and the i386 farm was rebuilt and SAVED to the cache
    (725 files), so the next build skips it. The pad's Swift is still
    uncompiled (Archive comes later). Scan of the workflow / build scripts
    for other stale research/ paths: only research/freetype/include in
    ntdll-unix / win32u-unix build.sh, identical upstream and harmless (those
    steps pass; the headers come from build/freetype-ios). Next: build 286 =
    this fix + the GoT GPU registry fix (c2ed0ab); main stays at the last
    green build until then. Build 286 dispatched (run 36870435733, head
    6182ab4).
  - **M1 iPad again, log GoW.exe 2026-10-01 14:56:44 (relayed 15:4x UTC+3):
    still build 277** (`[build] v0.1.277`), game-config=0 this time, 1280x720.
    Screenshot: fully black, only the Metal HUD (30 FPS, GPU 21.8 ms, App
    6.24 GB, Available 2.35 GB). The log is long (710k lines, 24,000 SM50
    shaders created) -> it got into gameplay, and the whole scene is black
    there. Same float targets as its 14:27 log: R32F 640x360 / 320x180 /
    20x12, RGBA32F 80x45, i.e. it renders internally at 640x360 (half of
    1280x720 per axis), where the 32x32 luminance tiles read/write furthest
    past the texture edge. Nothing new: 277 has neither the ld bounds (282)
    nor the UAV store bounds (284). The iPad user still has to install 284
    (or 286). Cheap check on that device: internal resolution 1080p (the
    owner's iPhone never darkens at native 1080p) -- if the scene appears,
    it is the same bug. Owner then relayed "he says he installed 282": the
    log contradicts it three ways (`[build] v0.1.277`, xtajit64 "compiled
    Oct 1 2026 10:38:37" = 277's build time, no `[ld-bounds]` line in 24,000
    shader conversions; 282 was ready at 12:32 UTC = 14:32 in Germany, the log
    is 14:56). Likely two Madeira apps side by side (different signing) or a
    failed install; told the owner to have him delete the old one and send a
    log whose line 13 says 0.1.284/286.
  - **Build 286 green** (run 36870435733, head 6182ab4, 2026-10-01 13:58
    UTC): upstream reorganisation merge + layout fixes + "Patch winemetal
    includes for the new layout" + DualSense/DirectInput HID pad (its Swift
    and main_ios.c compiled for the first time, clean) + the GoT stale-GPU
    registry fix. Native ABI 0851edda6a44a916. OTA: "bucket holds 10 builds,
    1.50 GB of the 8 GB budget", kurulum-0.1.286 written, install link
    e-mailed. main fast-forwarded to this branch; the duplicate push run is
    cancelled. Waiting on device: GoT past the GPU dialog (expect `[vgpu]
    removed the stale 106b:0001 adapter (3 keys) ...` on its first launch
    after God of War), God of War not regressed (it now removes the NVIDIA
    entry on launch), PS5 pad via game sheet "madeira-bcd: controller ->
    DirectInput / HID" or Session menu > Controller (`[hid-pad]` lines).
  - **GoT on build 286 (log GhostOfTsushima.exe 2026-10-01 17:04:41): the
    stale-adapter cleanup worked but did NOT fix the dialog.** `[vgpu]
    removed the stale 106b:0001 adapter (3 keys) ...` then `[vgpu]
    registered ...10DE&DEV_2544`, and still: probe device created ->
    destroyed -> "No installed graphics card" -> presents=0 after 30 s (the
    dialog was not dismissed). So the two-adapter hypothesis is refuted (the
    cleanup stays: it is correct and harmless). Ruled out as well: video
    budget (1536 MB in good and bad runs alike), module set before the probe
    (65 identical DLLs in 09-28 20:39 good / 20:41 bad / today), Wine's
    cleanup_devices (never runs on iOS: is_service_process() is always TRUE).
    External: on Linux (Bazzite issue #2102, Intel Arc B580) the same popup
    appears and **the game loads normally once it is closed**; on 09-28 20:41
    the owner closed it and the game went on too. -> Workaround: tap Tamam.
    Real bug found while looking: DXMT's nvapi.cpp copies every returned
    string with memcpy(dst, s.c_str(), s.size()) -- no NUL -- so
    NvAPI_SYS_GetDriverAndBranchVersion's branch string ("r<sdk>_000"),
    NvAPI_GetDisplayDriverVersion's strings, GetInterfaceVersionString and
    GPU_GetFullName carry whatever the caller's stack held after the text.
    That is a run-to-run varying input to the game's driver-info read and
    fits the intermittent pattern (not proven). Fix:
    tools/patch-nvapi-strings.py (5 copies -> bounded, terminated copy;
    tested on a copy after patch-dxmt-nvapi.py, idempotent; helper compiled
    and tested on the host), run by tools/build-dxmt-nvapi.sh. Named
    patch-nvapi-* so the i386 farm key (tools/patch-dxmt-*.py) is kept.
    Remaining inconsistencies, unchanged: NVAPI says driver 999.99 and
    "NVIDIA GeForce RTX 4090" (GetFullName) while DXGI / the registry say
    RTX 3060 (2544) with driver 35.0.15.6094 (560.94). If the dialog stays
    after this, next candidates are making those agree and logging the
    game's own text log again (the `[guest-log]` mirror is gone, see above).
  - **GoT dialog: the actual regression found (owner: "this worked three
    days ago, what happened?").** A normalised diff of the DXGI / D3D12 /
    vgpu lines up to the probe device, good 09-28 20:39 vs 17:04 today,
    shows one real difference: 09-28 logged `[monitor-identity] ml1190 using
    user32 primary=0x10001 (DXMT_WSI_MONITOR_IDENTITY=0 restores the
    synthetic handle)` -- default-on in this fork then -- and the user32 mode
    list ([mode-budget] ml1140, [dxgi-modes] count=19). Since the build 222
    switch to upstream's DXMT pin, dxmt/src/util/util_madeira_switch.hpp makes
    DXMT_WSI_MONITOR_IDENTITY and DXMT_WSI_MODE_TABLE "32-bit only" (off for
    64-bit modules unless the variable is set), so DXGI_OUTPUT_DESC::Monitor
    is the private sentinel, not user32's HMONITOR, and the game cannot find
    its monitor on the adapter -- which is what the dialog says ("...and your
    monitor is connected to it correctly"). GoT was not launched between
    09-28 and today, so nobody saw it. Fix (app/Madeira/LibraryBCD.swift
    applyExtras): with "Report an NVIDIA GPU" on, also export
    DXMT_WSI_MONITOR_IDENTITY=1 and DXMT_WSI_MODE_TABLE=1 (unset otherwise;
    a game file's env.NAME = 0 still wins, it is applied later). God of War
    (NVIDIA off) is not touched. Immediate test without a build: in GoT's
    game file add `env.DXMT_WSI_MONITOR_IDENTITY = 1` and
    `env.DXMT_WSI_MODE_TABLE = 1`. The earlier two hypotheses of today (two
    registry adapters; NVAPI strings) were wrong as the cause of THIS
    regression; their fixes stay (both are correct on their own). Host
    checks launch-routing / library-sections / config-catalog PASS.
    Build 288 (NVAPI strings) was cancelled by build 289 (run 36874555477,
    head b5579cd), which carries both.
  - **Owner: "the dialog is not even drawn, the screen is dark" -- second
    regression from the same switch.** 09-28's GoT log has the whole GDI path
    for the message box (`[surf-create]`, `[surf-flush]` x54, `[overlay] first
    window hwnd=0x10034 ...`, `[overlay-place] ... game-rect=440x248`,
    `[winios] present ...`); 17:04 today has none of it: the dialog is
    created (`[win-name]` "No installed graphics card ...", Tamam / Iptal)
    but never reaches the screen. That game-mode window overlay was 125hz's
    "direct-launch overlay" in app/Madeira/Winios/Winios.m (commit 855222e,
    merged with PR #28 as 47801f7 on 09-26; Winios.m was 3118 lines). The
    switch to upstream (merge 4ccfcb5, build 222, 09-29) took upstream's
    Winios.m (now 1765 lines), where GDI window surfaces are composited only
    in desktop mode (build/win32u-unix/driver_ios.c load_display_driver:
    pCreateWindowSurface = winios_CreateWindowSurface only when
    MADEIRA_DESKTOP=1; "Games keep the offscreen (invisible) surface path").
    So since build 222 **every message box a game opens is invisible** --
    not only GoT's. Open item, not fixed: porting the overlay back is ~1350
    lines against upstream's rewritten Winios.m (big, risky for God of War);
    alternatives to weigh: enable window-surface compositing in game mode
    only while a top-level dialog exists, or mirror a modal dialog's text and
    buttons into a native alert. Workarounds now: the on-screen Enter (↵)
    key should press the invisible dialog's default button (Tamam) -- not
    verified; GoT's dialog itself goes away with the monitor-identity fix
    (build 289, or the two env lines in its game file).
  - **Owner: "will the launcher (the small Play / Options box before DX12)
    show? It did before upstream." -> No, not without the overlay; so the
    overlay is back now (game-mode windows).** 09-28 20:39 shows the
    launcher: top-level hwnd 0x10038 "Ghost of Tsushima DIRECTOR'S CUT",
    792x447, drawn by the old overlay (`[overlay] first window hwnd=0x10038
    ... surface=896x512`) before the game window 0x2003a (1280x720) and its
    D3D12 swapchain. Without a game-mode window path GoT would sit at an
    invisible launcher even with the dialog gone, so build 289 alone could
    not work. Design (small, on upstream's desktop compositor instead of
    porting 125hz's ~1350-line overlay):
    * build/win32u-unix/driver_ios.c: `winios_game_windows()` (not desktop
      mode and MADEIRA_GAME_WINDOWS != 0) installs pCreateWindowSurface in a
      game session too, and forwards winios_window_frame for TOP-LEVEL
      windows only (not WS_CHILD, parent = the desktop window). Log
      `[winios] game mode: launcher / dialog windows are drawn over the game`.
    * app/Madeira/Winios/Winios.m: in a game session the compositor view is
      created as a transparent overlay (clear background, no teal backdrop,
      no touches, no drawn cursor) in the same game rect the front end
      publishes via winios_set_desktop_rect -- the rect MetalBackedView maps
      touches through, so a tap lands on the drawn button. A window is drawn
      only if its rect does NOT cover the whole guest desktop and it does
      not present through Metal (`winios_note_game_metal_hwnd`, called by
      IOSDisplayShim's game-mode view_create_metal_view, which D3D9/11/12
      swapchains all reach via CreateMetalViewFromHWND). Bits that arrive
      before a window's position wait in a hidden layer. The overlay is
      dropped at session end (winios_compositor_set_hidden(1)) and at every
      Wine start (`winios_session_reset`, WineProcessBridge), and a desktop
      compositor left from an earlier session of the same app run is
      replaced (and vice versa). Logs: `[winios] game-mode window overlay
      attached`, `[winios] game window hwnd=... presents through Metal`,
      `... not drawn (covers the guest desktop)`.
    * God of War: its window covers the guest desktop (1024x768 / 1280x720)
      and presents through Metal, so it is never drawn; with the old overlay
      (09-29 logs) the game window flushed GDI only 4 times per session, so
      the extra surface copies cost nothing measurable. Library starting
      screen: a drawn game-mode window counts as the session's first frame
      (as a desktop window does), so it no longer covers a launcher.
    * Not verifiable here (no Swift/UIKit compiler): first compile is CI.
      ConfigCatalog regenerated (env.MADEIRA_GAME_WINDOWS), check PASS;
      check-swap-coverage and check-wg-parser fail on HEAD too (pre-existing);
      the swift-needing host checks cannot run in this container.
  - **GTA V Enhanced (owner, logs PlayGTAV.exe 2026-10-01 17:30:35 /
    17:31:07 / 17:31:38, build 286; owner: "let's move several games at
    once").** All three end the same way after ~1-5 s: PlayGTAV.exe (the
    launcher stub) spawns `C:\Grand Theft Auto V Enhanced\GTA5_Enhanced.exe`
    (internal name game_win64_gdk_master_llvm.exe, the D3D12 GDK build) as a
    pseudo-process child, then exits (NtTerminateProcess(self, 0)) about a
    second later; WineProcessBridge treats the main process's exit as the end
    of the session and stops the wineserver, so the game dies while loading
    (`[Wine child thread] child exited with code -1073741819`, "Wine finished
    after 1.0s"). On Windows / Wine the server lives while any process does.
    Fix: build/ntdll-unix/process_ios.c keeps a table of running
    pseudo-process children (image basename + start time; slot taken in
    spawn_process, released at the end of ios_child_thread_entry) and
    exports `madeira_live_game_children(buf, len, max_age)`, which skips
    crash reporters / helpers (names containing crash, crs-handler, handler,
    report, helper). After the main process exits, WineProcessBridge waits
    (polls every 200 ms, logs every 60 s) while such a child runs -- but only
    if one was started in the last 60 s, so a game that exits normally long
    after starting a helper still ends at once (God of War / GoT start
    crs-handler.exe, which is a helper anyway). Logs: `[WineProc]
    madeira-bcd: the main process exited but N child process(es) it started
    still run (gta5_enhanced.exe) ...`, `... the last child process exited
    after N s`. MADEIRA_WAIT_CHILDREN=0 restores the old behaviour. The slot
    code was compiled and tested on the host in isolation (take / release /
    helper filter / age filter); the rest is first compiled by CI. Not
    looked at: anything GTA V does after this point (D3D12, its own checks).
    The launcher's command line carries `-nobattleye -scOfflineOnly`; this
    is a Madeira process-lifetime fix only (hard rule: nothing about crack or
    emulator setups).
  - **GTA5_Enhanced.exe started directly (log 2026-10-01 17:32:19, build
    286): the mirror image.** The game loads socialclub.dll, spawns
    `PlayGTAV.exe` (cmdline "PlayGTAV.exe") and terminates itself with exit
    code 0x1337 ~5 s in -- the usual "restart me through my launcher" -- and
    the session ended the same way (main process exit -> wineserver
    stopped). With build 291's child wait both starts should work: the main
    exe exits with PlayGTAV.exe running (started < 60 s ago) -> the session
    waits; PlayGTAV.exe then starts GTA5_Enhanced.exe (a grandchild, tracked
    in the same table, since every pseudo-process spawns through
    process_ios.c) and exits; the wait goes on while GTA5_Enhanced.exe runs.
    Expect `[WineProc] madeira-bcd: the main process exited but 1 child
    process(es) ... (playgtav.exe)` and later only gta5_enhanced.exe in the
    "still running" lines.
    API: the owner thought GTA V is D3D11. That is the Legacy edition
    (GTA5.exe, DX10/10.1/11). This install is the Enhanced edition
    (GTA5_Enhanced.exe, internal name game_win64_gdk_master_llvm.exe), which
    is D3D12-only and loads DirectStorage (DSTORAGE.dll, the game's own copy)
    at start-up; it got no further than that in these logs, so no d3d12.dll
    load is visible yet. It will run on madeira-d3d12 (the GoT path), not
    DXMT's D3D11. Owner (2026-10-01): no Legacy edition -- Enhanced only.
    Reference he raised: "Vapor" (StephenDev0, the StikDebug author;
    announced 2026-09-12, unreleased) showed GTA V on an iPhone 18 Pro Max
    (A20 Pro) at 66 FPS average in the benchmark's city drive, ~80 elsewhere,
    with press reports giving the settings as 1080p, **DirectX 11**, high
    textures, FXAA, MSAA off -- i.e. the DX11 (Legacy-style) renderer, not
    Enhanced's D3D12-only one, on a newer chip than our A19 Pro. Shows that
    the CPU translation side is feasible; not a like-for-like target for
    Enhanced on madeira-d3d12.
  - **DualSense / HID pad, first device test: WORKS in God of War (owner,
    build 286, screenshots 2026-10-01 ~17:40 UTC+3).** Session menu >
    Controller > Controller API = "DirectInput / HID", status "Live in this
    session" ("This session: DualSense (HID)"). God of War's settings and
    View Controls now show PlayStation prompts (Cross SELECT / Circle BACK,
    a DualSense drawing) instead of Xbox ones; menu navigation works. Same
    session, unchanged otherwise: 1280x720, ~53-56 FPS in the settings menu,
    App 5.4 GB, available 3.2 GB, thermal nominal. Owner: do not call it done
    before more games are tested. Still open: a DirectInput-only game, Ghost
    of Tsushima (libScePad), phase 2 (rumble / adaptive triggers /
    lightbar), phase 3 (touchpad coordinates, gyro).
  - **God of War at native 1080p: performance work started (owner
    2026-10-01: "1080p looks great; raise the FPS as far as possible; the
    darkening then does not matter; start an agent if needed").** The
    darkening below 1080p is parked. First look at the 1080p log
    (GoW.exe 15:06:44, build 279): `[rip-profile] ml1111/1112` puts ~43 % of
    RUNNING guest samples inside two kernel32.dll calls (IAT 0x140d48220 ->
    kernel32+0x374f0, 26 %; 0x140d48448 -> kernel32+0x409a0, 17 %;
    kernel32 at 0x71fe6d0000), and `[xp]` shows much of the game's CPU time
    on efficiency cores (e.g. P=189 ms vs E=278 ms in a 279 ms window).
    A background agent (own worktree; no push, no dispatch, no HANDOFF
    edits) is analysing it: name those two functions (or add a diagnostic
    that names IAT callees as module!export), thread QoS / P-core placement,
    GPU vs CPU bound, present latency, existing DXMT / sync switches; it
    writes docs/perf-gow-1080p.md and low-risk or switchable changes on its
    branch for the main session to merge and build.
  - **Build 291 green** (run 36877858410, head 05f67f3, 2026-10-01 14:57
    UTC; 288 / 289 / 290 were cancelled by it): monitor identity + mode
    table with "Report an NVIDIA GPU", game-mode launcher / dialog windows
    (Winios.m / driver_ios.c / IOSDisplayShim / WineProcessBridge -- the
    ObjC compiled first time), NVAPI NUL-terminated strings, launcher-child
    session wait (process_ios.c), plus everything of 286. Native ABI
    8c81d07a4878eaea, shader cache identity 19111887a738ea3a. OTA: "bucket
    holds 10 builds, 1.51 GB of the 8 GB budget", kurulum-0.1.291 mailed.
    main fast-forwarded (no workflow change since 286, so no duplicate run).
    Waiting on device: GoT launcher visible + no "No installed graphics
    card" (`[monitor-identity] ml1190 using user32 primary`, `[winios]
    game-mode window overlay attached`), GTA V Enhanced past the launcher
    (`[WineProc] madeira-bcd: the main process exited but ... still run`),
    God of War unchanged (its window must show `presents through Metal` /
    `not drawn (covers the guest desktop)`, never a drawn layer).
  - **GoW 1080p performance agent finished; its branch merged (862905a).**
    Full write-up: docs/perf-gow-1080p.md (Turkish summary on top). Findings
    from the 15:06:44 log, ranked: (1) the chip's shared power budget, not
    thread QoS -- during 1080p play the P cores sit at ~1.3 GHz doing 0-0.9
    cores of work while the process uses ~3.4 E cores at 1.6-1.7 GHz, 6-8
    threads in the run queue, CPU power only 0.45-0.8 W; the GPU takes the
    budget (guest threads are already USER_INTERACTIVE, ECO was off). (2) the
    wineserver is the 2nd-busiest thread (~47 % of an E core, 10-16k
    requests/s, select + release_semaphore = the game's job semaphores;
    fastsync runs with sem=off; a madsync run on 09-30 had 249 req/s). (3)
    per-thread CPU: DxRenderThread 179 ms / 300 ms, main 131,
    TaskManager00-03 ~87 each, dxmt-encode 58. (4) the "43 % inside
    kernel32" was a profiler artefact: the calls are kernel32!Sleep and
    kernel32!GetCurrentThreadId, RUNNING includes queued threads and FEX's
    guest RIP is stale; [cpu-split] puts most host time in sched_yield.
    (5) ~280 Mach exceptions/s from GetProcAddress'd functions called at
    their PE address (DXMT logger __wine_dbg_output ~50 %, libc++ atomic
    wait's WaitOnAddress / RtlWakeAddressAll ~45 %). (6) DXMT logs ~130
    lines/s at Info level. (7) GPU time was never logged.
    Merged (all diagnostics or default off): ml1112 names IAT callees
    (`kernel32.dll!Sleep (import KERNEL32.dll!Sleep)`); `[xp-api]` counters
    for D3D11 games (follows the busiest process, ml1131c); `[frame]`
    instrument in server_ios.c (was empty stubs in virtual_ios.c) behind
    `MADEIRA_FRAME_STATS=1`, fed GPU start/end by
    tools/patch-winemetal-gpu-span.py (new CI step "Patch winemetal GPU
    timeline for [frame]", native only); `MADEIRA_PROBES=light|0`. After the
    merge: ConfigCatalog regenerated (check PASS), the whole DXMT patch
    chain applied on a scratch copy in CI order and re-applied idempotently,
    check-fastsync / launch-routing / library-sections / hidpad PASS.
    Proposed, not done: translate arm64x_check_call targets to the pool copy
    (upstream, committed PE ntdll), FEX fast path for trivial getters, no
    yield before a timed Sleep, framebufferOnly when MetalFX / framegen are
    off, GPU work reduction once [frame] shows numbers. Owner tests on the
    next build, one at a time in God of War's config, same outdoor spot 3-5
    min, HUD screenshot each: `inproc-sync = 1` (Madsync; biggest CPU lever),
    `env.DXMT_LOG_LEVEL = none` (+ drop env.WINEDEBUG), MetalFX off at
    native 1080p, `env.DXMT_WAIT_ON_ADDRESS = 1` (moderate risk),
    `env.MADEIRA_LD_BOUNDS = 0` (native 1080p only; re-converts shaders);
    with `env.MADEIRA_FRAME_STATS = 1` in the game config and
    `env.MADEIRA_DEVICE_STATS = 1` in madeira.cfg.
  - **M1 iPad, build 291 (log GoW.exe 2026-10-01 17:08:27; owner: not a
    priority).** Now really on 291 (`[build] v0.1.291`, `[ld-bounds] ... on`).
    Display 640x480, game file only `fence-chain = 6`; internal targets
    320x200 / 160x100 / 40x25 / 10x7. The exposure readback (`[rb-buf]
    value 16 bytes`) is not spiky like the iPhone's but stuck: starts as
    `nan 0.2331 nan`, then mostly `19.9326 0.2331 6500.36` (x = log
    luminance ~19.9 vs ~-0.15 on the owner's iPhone outdoors, z = 6500 vs
    ~1500), later the exposure factor falls to ~0.0156 with x 5.9-7.2. So the
    game measures an absurdly bright (or NaN) scene and crushes exposure to
    black: NaN / Inf in the HDR scene or its luminance chain on Apple7 (M1),
    not (only) out-of-range reads. Cheap next try on that device:
    `env.MADEIRA_PS_CLAMP = 1` (finite clamp of pixel-shader outputs, build
    277; did not help the iPhone's spikes, but this one looks like NaN/Inf),
    then `= 2`. Parked behind GoW 1080p performance, GoT and GTA V.
  - **Build 291 device results (owner, logs 2026-10-01 18:37:52 PlayGTAV,
    18:38:27 GTA5_Enhanced, 18:38:48 GhostOfTsushima).**
    * GTA V: the session wait works (`[WineProc] madeira-bcd: the main
      process exited but 1 child process(es) ... still run (gta5_enhanced.exe)`
      / `(playgtav.exe)`), but the game child itself crashes ~1-2 s in: tid
      002c, AV READ of 0 in FEX JIT code (insn f9400021 ldr x1,[x1]), guest
      RIP = the child's pool copy of ntdll's x64 syscall thunk (ntdll
      +0x87050, `jne; syscall; ret; int 2e; ret`), handler in RUNE64.dll,
      unwind fails -> NtTerminateProcess 0xC0000005. The same path runs in
      the MAIN process (GTA5_Enhanced as main: `[pool-rip-fix] guest RIP ...
      POOL-COPY alias of PE 0x71ffd57050 -- redirecting` x24, no crash), so a
      child pseudo-process lacks something. Agent started (own worktree):
      root cause + Madeira-side fix or diagnostics, docs/gta5-child-crash.md.
    * GoT: `[monitor-identity] ml1190 using user32 primary=0x10001` is on and
      the dialog STILL appears -> the monitor-identity theory is refuted as
      the (only) cause; agent started (own worktree): diff good 09-28 vs now
      for everything the game can observe (DXGI, NVAPI, registry, D3DKMT,
      madeira-d3d12 probe answers vs pack 5 69d7311), restore a guest
      text-log mirror if feasible, docs/got-gpu-check.md.
    * GoT dialog still invisible on 291: the overlay attached and created a
      layer for the dialog (hwnd 0x10034) and `[surf-create] ... RECREATED
      -- old content dropped`, but no `[surf-flush]` ever followed -- the
      window painted into its first surface and nothing asked it to repaint.
      The old driver sent an expose-equivalent NtUserRedrawWindow
      (RDW_INVALIDATE|ERASE|FRAME|ALLCHILDREN) for a visible surface-backed
      window that was just shown or got a new surface; ported into
      winios_drv_window_pos_changed for game mode only (desktop mode
      unchanged). The owner pressed Enter / Esc on the on-screen keys and
      tapped blindly (`[winios] post_key vk=0xd`, `post_touch_down x=331
      y=492`); the dialog stayed.
  - **Build 292 green** (run 36885317238, head c683d1c): the GoW 1080p
    diagnostics ([frame] behind MADEIRA_FRAME_STATS=1, ml1112 callee names,
    [xp-api] for D3D11, MADEIRA_PROBES). Native ABI 30a3cfb8d9a86173, shader
    cache identity unchanged (19111887a738ea3a), OTA mailed, bucket 10
    builds 1.51 GB. main fast-forwarded to c683d1c (not further: 873fd2c was
    not built yet); the push run 293 it started was cancelled (the merge
    changed build-ipa.yml). **Build 294** dispatched from 873fd2c (run
    36887895386): 292 + the game-mode repaint fix.
  - **GTA V child crash: root cause found (agent), merged as 7212ed5;
    details docs/gta5-child-crash.md.** Every x64 pseudo-process loads its
    own FEX (libarm64ecfex.dll) with its own alias table, but
    unixcall_ios_push_jit_aliases (virtual_ios.c) skipped every
    owner-tagged JIT mapping, so a child's emulator mapped ntdll to the
    PARENT's pool copy and never learned its own. An x64 syscall (RUNE64.dll
    calling ntdll's x64 stub, NtProtectVirtualMemory) ends in ntdll
    dispatch_syscall setting Pc to the process's own pool copy of
    invoke_arm64ec_syscall (ntdll+0x87050); FEX's [pool-rip-fix] could not
    map it back (`[iOS-xquery] MISS tracker=... addr=0x14fc2f050`), "NoExec
    instruction in entry block" -> FEX's GuestSignal_SIGSEGV trampoline (the
    `ldr x1,[x1]` with x1 = 0 is its deliberate fault, not a data bug) ->
    unwind through RUNE64's handler fails -> 0xC0000005. Not GTA-specific:
    crs-handler.exe died the same way in the GoT logs of 09-26..09-28.
    Correction: in the GTA5_Enhanced-first log the dying child (tid 002c)
    is PlayGTAV.exe, not a grandchild. Fix (build/ntdll-unix only): the
    drain pushes the registering process's OWN copy instead of the parent's
    (a main process owns none, so it is unchanged); a child's private ntdll
    copy also gets the RtlPcToFileHeader pool-alias patch (loader_ios.c
    wine_ios_child_main); the alias-push callback is dropped when the
    process owning it exits (it pointed into freed pool memory); `[alias-
    push] madeira-bcd ...` diagnostics. Switch: MADEIRA_CHILD_OWN_NTDLL=0.
    tests/host/check-child-ntdll-alias.py PASS (replays the build 291
    layout); catalog check PASS after the merge. Found, not fixed: the
    alias-push callback is global -- the last process to register an
    emulator receives every later image (GoW 15:52:42: after crs-handler
    registers, GoW's xaudio2_9 / mfplat / mmdevapi / dsound aliases went to
    crs-handler's emulator, so GoW's x64 calls into them take the ~33 us
    exec-fault redirect -- a possible GoW performance item; the new lines
    measure it). FEX never retires a dead process's JIT ranges.
  - **Owner (2026-10-01 ~19:15 UTC+3): God of War is dark overall now,
    much darker in some scenes, "never looks normal".** No log yet; build /
    resolution not stated. Native 1080p looked right on build 279 (log
    15:06:44); the texture-load bounds (282) and typed-UAV-store bounds
    (284) are default-on since then and were only ever judged at 720p.
    Asked for the A/B `env.MADEIRA_LD_BOUNDS = 0` (turns both off; first
    launch re-converts shaders), screenshots of the same spot with and
    without it, the session log (292 has the [rb-buf] exposure values), and
    whether the in-game brightness / HDR setting changed. If it is the
    bounds checks, make them default-off.
  - **Build 294 green** (run 36887895386, head 873fd2c): 292 + game-mode
    repaint fix. Native ABI 50ece7417b95bb00, OTA mailed, bucket 10 builds
    1.51 GB; main fast-forwarded to 873fd2c (no workflow change, no push
    run). **Build 295** dispatched from cfec843 (run 36890462072): 294 + the
    GTA V child-ntdll fix (7212ed5).
  - **GoT "No installed graphics card": the real regression found (agent),
    merged as f5baf40; details docs/got-gpu-check.md.** The 09-26 19:58 log
    shows GoT's order: NVAPI enumerates the GPU -> DXGI GetDesc ->
    EnumDisplayDevices(NULL, 0) -> NvAPI_GetAssociatedNvidiaDisplayHandle /
    GetAssociatedDisplayOutputId -> EnumDisplayDevices("\\.\DISPLAY1", 0,
    EDD_GET_DEVICE_INTERFACE_NAME) -> probe device -> "[NxApp] Failed to get
    GPU Driver Info" -> dialog: it builds an adapter -> NV display ->
    output -> monitor-interface table. The same calls happen in good and bad
    runs; the ANSWERS differ: 17088ab (09-29, "upstream's sysparams_ios.c
    with our GPU registration on top") dropped the fork's virtual-monitor
    identity -- GetMonitorInfo now names the monitor "WinDisc" (Windows' name
    for a disconnected display) instead of "\\.\DISPLAY1", and the
    synthesized monitor EnumDisplayDevices returns an empty DeviceID /
    DeviceKey (was `\\?\DISPLAY#Default_Monitor#...` and the class key);
    with "WinDisc", DXMT's NvAPI_DISP_GetDisplayIdByDisplayName fails for
    "\\.\DISPLAY1" too. So today's three earlier theories (stale adapter,
    NVAPI strings, DXGI monitor identity) were not it; they stay (correct on
    their own; the NUL fix probably explains the one intermittent failure on
    09-28 20:41). Ruled out by source diffs: dxgi (old pin 462a77e vs
    a5e0cd3), nvapi.cpp, madeira-d3d12 pack 5 vs HEAD for the probe,
    winemetal, wine d3dkmt and the PE DLLs. Changes:
    * build/win32u-unix/sysparams_ios.c: GetMonitorInfo says
      "\\.\DISPLAY1" again; the synthesized monitor EnumDisplayDevices gets
      the pre-222 DeviceID (interface path with
      EDD_GET_DEVICE_INTERFACE_NAME, `MONITOR\Default_Monitor\{4D36E96E-...}
      \0000` without) and DeviceKey; adapter answers unchanged;
      `MADEIRA_VMON_IDS=0` restores upstream's. Logs `[vmon]`, `[vmode] ...
      flags= cb= id= key=`, `[vdcfg]`, `[vkmt]`.
    * tools/patch-wine-guest-log.py (CI step "Patch wine with the game
      text-log mirror", before Build ntdll-unix; patches
      wine/dlls/ntdll/unix/file.c in place, no cache-key change): the
      `[guest-log]` mirror of a game's own *.log lines is back (125hz's old
      NtWriteFile mirror lived in their wine, not in this repo). Default:
      error / gpu / driver / adapter / display / nvapi lines, 64 per
      session; MADEIRA_GUEST_LOG=all (400) or =0; MADEIRA_GUEST_LOG_LIMIT.
    * tools/patch-nvapi-trace.py (run by build-dxmt-nvapi.sh): the
      `[nvapi] query` trace now goes through DXMT's Logger (the fprintf
      never reached a log), 30 adapter / display / driver entry points log
      `[nvapi] NvAPI_X -> status`; GetDisplayIdByDisplayName returns the
      primary display for the primary adapter's name.
    Host checks check-vmon-identity / check-guest-log / check-nvapi-trace
    PASS (the agent also built nvapi64.dll with llvm-mingw as CI does);
    after the merge: catalog regenerated (PASS), nvapi chain
    (dxmt-nvapi -> nvapi-strings -> nvapi-trace) and the guest-log patch
    applied on copies and re-applied idempotently. God of War risk low: no
    EnumDisplayDevices in its logs, NVIDIA reporting off (no NVAPI), and
    "\\.\DISPLAY1" is what every build up to 221 answered;
    env.MADEIRA_VMON_IDS = 0 / env.MADEIRA_GUEST_LOG = 0 undo it. Still
    open, identical in the good run: NVAPI says RTX 4090 / 999.99 / PCI id
    0x000010DE vs DXGI + registry RTX 3060 10DE:2544 / 35.0.15.6094.
    Build 295 was cancelled for **build 296** (run 36891112764, head
    5981d3e): 294 + GTA child-ntdll fix + GoT virtual-monitor fix +
    [guest-log] + NVAPI trace.
  - **GoW darkening below 1080p: owner wants it solved ("1080p aşağısında
    hala karanlık"); agent started (own worktree).** New logs, build 294,
    both with env MADEIRA_LD_BOUNDS=0 (bounds checks off), PAD_MODE=hid:
    19:16:44 at 720p = dark (float targets include R32F 754x424 and RGBA32F
    95x53 -- the game renders internally at 754x424 there), 19:33:23 at
    1080p = normal. The owner's earlier "dark overall" (bounds ON) has no
    log, so it is open whether the 282/284 bounds checks darken 1080p. The
    agent gets every known fact (tile grid past the bottom, exposure
    readback, iPad NaN, refuted switches) and checks resinfo / sampling of
    NPOT float targets / groupshared + barriers + atomics in compute /
    NaN-Inf semantics / render-target size vs viewport and stale regions;
    deliverables docs/gow-darkening.md, a fix with evidence or a set of
    independent opt-in experiment switches (each with its own shader-cache
    salt) for one A/B device session, and possibly an opt-in DXBC/AIR dump
    of the luminance shaders. Owner's correction: FSR 2 was on by mistake in
    the 19:16:44 720p log (hence 754x424); native 720p without FSR is just
    as dark -- passed on to the agent, with the list of all of today's GoW
    logs (sub-1080p dark: 11:03, 11:46, 11:49, 11:56, 14:03-14:23 x6,
    14:51, 15:52, 19:16; 1080p normal: 15:01, 15:06, 19:33).
  - **Build 296 green** (run 36891112764, head 5981d3e, 2026-10-01 16:39
    UTC): GTA V child-ntdll fix + GoT virtual-monitor identity + [guest-log]
    mirror + NVAPI trace on top of 294. Native ABI 2fb57e670bf63f47, shader
    cache identity unchanged, OTA mailed, bucket 10 builds 1.51 GB. main
    fast-forwarded to 5981d3e; the push run 297 was cancelled (the
    guest-log step changed build-ipa.yml). Waiting on device: GoT (no
    dialog, second D3D12CreateDevice, launcher visible; `[vmon]`, `[vmode]
    ... id=`, `[nvapi]`, `[guest-log]`), GTA V both ways (`[alias-push]`,
    child `[pool-rip-fix]`, no NoExec), GoW unchanged.
  - **GTA V on build 296 (logs PlayGTAV 19:53:36, GTA5_Enhanced 19:54:23):
    the child crash is FIXED and the game gets much further.** The child's
    emulator maps ntdll to its own copy (`[alias-push] ... own copy
    0x14fba8000`), `[pool-rip-fix] #1 guest RIP 0x14fc2f050 ... PE
    0x71ffd57050` in the child, no NoExec. Both start paths now run the game
    child (via PlayGTAV, and GTA5 -> PlayGTAV -> GTA5 grandchild). New stop:
    after socialclub / RUNE64 the game writes twice into its own read-only
    image (`[fault_rip] ... addr=0x140265bd5 kr=2(PROTECTION_FAILURE)`, then
    0x14122be51; `[exc-disp] raise ... c0000005 p0=1`), loads D3D12 / DXGI /
    winemetal, Streamline (sl.interposer, common, dlss, dlss_g, pcl,
    reflex) and nvapi64, creates a D3D12 device at feature level 12_0
    (0xc000), destroys it, writes its own crash report
    (`[guest-log] file .../Rockstar Games/GTAV Enhanced/CrashLogs/
    crashcontext.log`; only "GRAPHICS INFO / Display 1920 x 1080" passed the
    mirror's filter) and terminates with 0x80000003 (breakpoint). The
    GTA agent was resumed on these logs; the owner is asked for a run with
    `env.MADEIRA_GUEST_LOG = all` in GTA's game file so the whole crash
    report is mirrored.
  - **GoT on build 296 (log GhostOfTsushima.exe 2026-10-01 20:08:38 +
    screenshot): the launcher dialog is now DRAWN, but it takes no input
    (no cursor, taps / Enter / Space do nothing) and the game's own log still
    says "Unable to find active GPU".** The `[guest-log]` lines show why:
    `[Monitor] Description : Apple A19 Pro GPU / Vendor : nVidia (10de) /
    Device : 0`, then NxApp lists "Wine Adapter" and "NVIDIA GeForce RTX
    3060" and finds neither. **Root cause: the DXMT_CONFIG separator.**
    DXMT splits DXMT_CONFIG on ";" only (`dxmt/src/util/config/config.cpp`
    `str::split(confLine, ";")`, unchanged since bc6d4c7) and a newline is not
    whitespace to its line parser, but the app joined the options with "\n"
    (`ContentView.swift` `parts.joined(separator: "\n")`, LibraryBCD
    `dxmtExtra.joined(separator: "\n")`, and ml1095 even turned ";" in
    madeira.cfg `dxmt` into "\n"). With the game's `metalfx = 2.0` the
    value became `dxgi.customDeviceId=2544\nd3d11.metalSpatialUpscaleFactor=2.0`
    (log lines 31-32 "DXMT config: ... via the game's settings", 8733-8734
    "Found config env: ..."), i.e. ONE option whose value is not 4 hex
    digits, so `parsePciId` returned -1 and DXGI reported Device 0 (and the
    MetalFX factor was never set either). On 2026-09-28 GoT had no MetalFX,
    so the config was the single `dxgi.customDeviceId=2544` and the check
    passed. The earlier trails (stale registry adapter, NVAPI strings,
    monitor identity, virtual monitor name) were real differences but not
    this check. **Fix (this commit):** every source (madeira.cfg `dxmt`, the
    game file's `dxmt`, MADEIRA_DXMT_EXTRA) is split on ";" and newlines,
    trimmed, and the options are joined with ";"; LibraryBCD joins its extras
    with ";". Any game that combined two DXMT options (e.g. GoW's
    `dxmt = d3d11.mipClampBC=2` plus MetalFX or the NVIDIA switch) had the
    same silent loss. Catalog regenerated (`dxmt` note), check PASS.
    Workaround on 296: MetalFX off for GoT. **Expected on the next build:**
    `Found config env: dxgi.customDeviceId=2544;d3d11.metal...` and `Device :
    9540` (0x2544) in `[guest-log]`. **Open:** input to the game-mode
    dialog (no cursor in game mode; taps / keys not delivered), the extra
    "Wine Adapter" in NxApp's adapter list, `[vkmt] D3DKMTEnumAdapters2 -> 0
    adapters`.
  - **GTA V agent finished on the 296 logs; merged (9fe3ceb + 80ed5fb, merge
    db2e07d).** The 0x80000003 is the game's own deliberate `int3` at
    GTA5_Enhanced.exe RVA 0x100798 with RSI = 0x17b133bd = joaat
    `ERR_GFX_D3D_NOD3D12` ("DirectX 12 adapter or runner not found"): the
    first int3 is handled by the game, the second is fatal, then it writes
    crashcontext.log and exits (PlayGTAV 19:53:36 lines 6734-7114). No
    D3D12CreateDevice after the probe device (4654-4677): the game rejects
    the adapter during DXGI enumeration, after Streamline loads
    (`NvAPI_Initialize -> -6` x6, `D3DKMTEnumAdapters2 -> 0 adapters`). The
    two writes into the read-only image are FEX's self-modifying-code path
    and are handled ("Handled self-modifying code", "store landed").
    **Bug fixed (child only):** `top_window stays 0` x9 on the game thread
    -- init_user runs once per iOS process, so only the session's first
    pseudo-process registered the desktop / message classes (wineserver
    keeps classes per process); a launcher main that never opens a window
    leaves the child without GetDesktopWindow(), GetDC(NULL) and its first
    top-level window. `get_desktop_window` (winstation_ios.c) now, only on
    failure, never in the session process and once per process, registers
    the classes for the child and retries; with no thread desktop it runs
    `winstation_init` and retries once more. `MADEIRA_CHILD_DESKTOP=0`
    turns it off; `[child-desktop]` logs it. `tests/host/check-child-
    desktop.py` PASS (also with the switch off); child-ntdll-alias and the
    catalog check PASS after the merge. Not yet proven to clear the abort.
    **Next GTA test (build after 296):** `env.MADEIRA_GUEST_LOG = all`, look
    for `[child-desktop] ... top_window=0x...`, the full crashcontext.log in
    `[guest-log]`, and a D3D12CreateDevice after the Streamline loads. If
    still RSI=0x17b133bd: try "Report an NVIDIA GPU" for GTA (DXMT_ENABLE_
    NVEXT + monitor identity + mode table; the 64-bit DXGI output otherwise
    has a placeholder monitor and 3 modes, the game expects 1920x1080).
    Other suspects (not changed): D3DKMT lists no adapter, DXMT has no
    IDXGIFactory7, OutputDebugString is logged only 4x per process.
  - **GoT dialog takes no input (owner, build 296, log 20:08:38: "no mouse,
    Enter / Space do nothing") -- cause found and fixed.** The box is the
    game's "No installed graphics card" MessageBox (hwnd 0x10034, buttons
    "Tamam" / "İptal", thread 0024). The app posted 18 touches (one at
    552,424, right on "Tamam") and 36 keys (`[winios] post_touch_down`,
    `post_key vk=0xd / 0x20 / 0x9`), but the log has **no `[winios] drain`
    line at all**: the ring in Winios.m is only drained when a wine thread
    runs pProcessEvents (PeekMessage / wait_message). A game's render loop
    polls every frame (GoW 10-01 14:06: drain=22), but a modal loop sleeps
    in `wait_message` with no timeout and the wineserver does not watch the
    ring, so nothing ever delivered the input. Desktop mode has woken these
    waits every 16 ms since the trackpad work; game mode did not. **Fix:**
    `driver_ios.c` marks (thread-local) a thread that shows a visible,
    surface-backed top-level window smaller than the guest desktop (>= 32x32,
    WS_VISIBLE, its own thread) -- a launcher or message box, never a
    full-screen game window -- and `message_ios.c` `wait_message` uses the
    desktop-mode 16 ms slicing for that thread. `[game-input] madeira-bcd
    tid=... hwnd=...` once per thread; `MADEIRA_GAME_INPUT_WAKE=0` turns it
    off. Host syntax check of driver_ios.c / message_ios.c with -Wall clean;
    catalog regenerated, check PASS. Cost: a marked thread that later sleeps
    in a message wait wakes ~60x/s (cheap); GoW's full-screen window does not
    mark its thread. No cursor is drawn in game mode (by design, desktop
    sessions only); taps act as absolute clicks. **Expected on the next
    build:** `[game-input] ... hwnd=0x...` when the box appears, then
    `[winios] drain type=0 ...` / `drain type=1 ...` after taps / keys, and
    the box closes on "Tamam" or Enter. With the DXMT_CONFIG fix above the
    box itself should no longer appear for GoT.
  - **GTA V Enhanced, build 296 with `env.MADEIRA_GUEST_LOG = all` (log
    PlayGTAV.exe 2026-10-01 20:16:49): the cause of ERR_GFX_D3D_NOD3D12 is
    IDXGIFactory7.** The full crashcontext.log is mirrored (lines 6815-6951):
    "Game State : System Init", **"GRAPHICS INFO / Factory : None"**, Display
    1920 x 1080, nothing else useful. The decisive line is 6662, right after
    dxgi.dll loads on the game thread 0034: `warn: DXGIFactory: Unknown
    interface query a4966eed-76db-44da-84c1-ee9a7afb20a8` = **IDXGIFactory7**.
    DXMT's factory (`dxmt/src/dxgi/dxgi_factory.cpp`) answers only up to
    IDXGIFactory6, the game's factory stays NULL, three GetDesktopWindow
    calls follow (`top_window stays 0`) and then the int3 with RSI=0x17b133bd
    (6671-6742), exit 0x80000003 (7139). The probe D3D12 device earlier in
    the run (4650-4679) is fine. **Catch:** the 64-bit `dxgi.dll` is
    upstream's committed binary (9e8291e); CI does not build it, so a source
    fix needs CI to build dxgi.dll for arm64ec from the dxmt submodule.
    **An agent was started** (worktree) to add IDXGIFactory7 via a patch
    script (not `patch-dxmt-*`, which is in the i386 cache key), build
    dxgi.dll from source in CI, check that the committed binary matches the
    submodule source, and keep upstream's binary selectable by a switch so
    God of War / Ghost of Tsushima cannot regress. Open until it reports.
  - **GoW below-1080p darkening agent finished; merged (c47dbc5, merge
    2da3dd3). Root cause NOT proven yet; nothing changes by default.**
    Evidence (docs/gow-darkening.md): in the still title menu the game's
    exposure readback (`[rb-buf] x e z w`) depends on the internal
    resolution -- 1920x1080 x 4.37 / z 4460, 1280x720 2.26 / 3120, 754x424
    (FSR) -0.84 / 1095 -- so below 1080p the luminance chain reads wrong,
    mostly black, input; a sampler with border colour (32,32,32,32) that
    Metal turns into 1.0 is created just before the luminance targets.
    Ranked candidates: edge / stale-binding reads (border colour, missing
    D3D11 hazard rules -- both PE d3d11.dll side --, out-of-range typed
    buffer / atomic / resinfo), warp-synchronous groupshared reductions,
    DontCare tile memory, fast math, sample_l bias, NaN/Inf. **Added, all
    OFF by default** (converted shaders byte-identical, cache salt
    unchanged without a switch): `tools/patch-airconv-gow-experiments.py`
    (`MADEIRA_TGSM_SYNC`, `MADEIRA_SAMPLE_L_BIAS`, `MADEIRA_PRECISE_MATH`,
    `MADEIRA_BOUNDS_EXTRA`, `MADEIRA_SHADER_DUMP`, each with its own salt),
    `tools/patch-winemetal-gpu-trace.py` (`MADEIRA_GPU_TRACE=T[,S[,N]]`,
    `MADEIRA_BORDER=black`, `MADEIRA_RP_LOAD=1`; `[gpu-trace]`, `[gpu-val]`,
    `[rb-src]`, at most 8 `[border]` lines by default), two CI steps right
    after "Patch winemetal GPU timeline for [frame]",
    `tests/host/check-dxmt-patch-chain.py` (all 21 workflow patch scripts in
    order, twice: PASS here after the merge), `tools/host-airconv.sh`.
    Catalog check PASS (the switches live in patched submodule code, not in
    the catalog). First real compile of the winemetal hooks is in CI.
    **Owner's device plan:** 7 runs, docs/gow-darkening.md section 6 (720p
    with `env.MADEIRA_GPU_TRACE = 45,2,4` + 1080p reference, then
    `MADEIRA_BORDER = black`, `MADEIRA_RP_LOAD = 1`, `MADEIRA_TGSM_SYNC = 1`
    + `MADEIRA_BOUNDS_EXTRA = 1`, `MADEIRA_PRECISE_MATH = 1`, FSR with
    `MADEIRA_SAMPLE_L_BIAS = 1`); success = menu `[rb-buf]` ~4.37 / 4460 at
    720p. A PE-side cause (border colour, hazards) would need d3d11.dll
    built from source -- the same question as GTA's dxgi.dll (agent running).
  - **Owner's build-296 runs (2026-10-01 20:26-20:41 UTC+3):**
    - **GoT 20:26:49, MetalFX off (the workaround): the GPU check PASSES**
      -- `DXMT config: dxgi.customDeviceId=2544` alone, `[NxApp] NVIDIA
      GeForce RTX 3060 (active)`, "Successfully found GPU Driver Info",
      "Driver Version: 560.94" (log lines 37, 9023-9025, 9787-9788). This
      confirms the DXMT_CONFIG separator diagnosis (a1abebf).
    - **GoT rendering corruption remains** (owner + recording
      ScreenRecording_10-01-2026_20-40-37): "with FSR off the artefacts got
      clearly angular / blocky; with FSR they were more rounded" -- i.e. made
      at internal resolution before the upscaler. **An agent was started**
      (worktree) on it with every GoT log / recording / screenshot since
      09-26 (frames via a pip imageio-ffmpeg), the earlier black-squares
      work (builds 192-198), and candidates with a block footprint (BC 4x4
      decode, wave / groupshared conversion, aliasing, barriers). Writes
      docs/got-corruption.md; open until it reports.
    - **GTA V 20:41:45 with "Report an NVIDIA GPU" on:** NvAPI now answers
      (`NvAPI_Initialize -> 0`, one physical GPU), but `Unknown interface
      query a4966eed...` (IDXGIFactory7) still appears twice (4660, 5339)
      and the game writes its crash report at "System Init" again (7432).
      Factory7 stays the blocker; passed on to the dxgi agent.
  - **Build 300 green** (run 36899052316, head 5eb58ff, 2026-10-01 17:45
    UTC): DXMT_CONFIG ";" separator (GoT), game-mode dialog input wake,
    GTA child desktop window. main fast-forwarded to 5eb58ff (no workflow
    change, so no push run). **Build 301 dispatched** (run 36901860397, head
    ab800bb): 300 + the GoW darkening experiments (two new CI steps; first
    real compile of the winemetal trace hooks).
  - **dxgi agent finished; merged (03ba1a1, merge 639cbff): GTA V's
    IDXGIFactory7, opt-in per game.** `tools/patch-dxgi-factory7.py` (on a
    copy of `dxmt/src/dxgi/dxgi_factory.cpp`; submodule untouched; name kept
    out of the i386 `patch-dxmt-*` cache key): MTLDXGIFactory derives from
    IDXGIFactory7 and answers it; RegisterAdaptersChangedEvent -> S_OK with
    a cookie (never signalled), Unregister -> S_OK; **EnumAdapterByLuid now
    works** (matched by the Metal registry-ID LUID that madeira_d3d12
    reports; was E_NOTIMPL); `[dxgi-src]` line once per process.
    `tools/build-dxgi-dll.sh` + CI step "Build dxgi-src.dll" (continue-on-
    error, right after the llvm-mingw cache, before every DXMT patch step and
    nvapi) builds the arm64ec dxgi.dll like DXMT's meson release build and
    ships it as **`arm64ec-windows/dxgi-src.dll` beside upstream's
    dxgi.dll** (never overwritten); exports must equal the committed DLL's;
    a failure warns and ships nothing. **Evidence the committed binary IS
    our pin:** the agent rebuilt it unpatched on Linux with llvm-mingw
    20260421 (macOS target libs): .text/.rdata/.data/.rsrc/.reloc byte-
    identical, all 9663 symbols at the same addresses, same imports/exports
    (only timestamp / build-id / dead .pdata differ) = DXMT a5e0cd3 release.
    The patched build differs only in the factory code; vtable slots 30/31
    are new (upstream's slot 30 is the destructor, so a binary hack was
    impossible). **Switch:** `env.MADEIRA_DXGI_SRC = 1` in a game's file
    (WineProcessBridge.m links dxgi-src.dll as system32\dxgi.dll in x64
    sessions and sysx64\dxgi.dll, after the per-session relink -- every
    session relinks all DLLs from the bundle, so other games always get
    upstream's dxgi.dll). Default off for all games (GoW / GoT untested with
    it). Host checks after the merge: check-dxgi-factory7, config catalog,
    patch chain PASS; workflow YAML parses. Only CI (macOS bash 3.2, Xcode)
    and the device can show the rest. **GTA test:** game file
    `env.MADEIRA_DXGI_SRC = 1` + `env.MADEIRA_GUEST_LOG = all`; expect
    `[WineProc] MADEIRA_DXGI_SRC=1: dxgi.dll -> dxgi-src.dll`, `[dxgi-src]
    ... a5e0cd3`, NO `Unknown interface query a4966eed`, a D3D12CreateDevice
    with a non-NULL adapter after the sl.* loads, no int3 RSI=0x17b133bd. If
    `EnumAdapterByLuid: no adapter with LUID` shows, the LUIDs disagree;
    next suspect D3DKMT (`D3DKMTEnumAdapters2 -> 0 adapters`). Remaining
    DXGI gaps (not fixed): GetSharedResourceAdapterLuid, occlusion / stereo
    registration, CreateSwapChainForComposition / CoreWindow (E_NOTIMPL),
    budget notification without madeira-dxgi-budget.txt, UMD version ~0.
  - **Build 301 green** (run 36901860397, head ab800bb, 2026-10-01 18:03
    UTC): 300 + the GoW darkening experiments (the winemetal trace hooks
    compiled). main fast-forwarded to ab800bb; that push started run 302
    (workflow changed), cancelled. **Build 303 dispatched** (run
    36904068206, head 2292a4b): 301 + dxgi-src.dll / MADEIRA_DXGI_SRC.
  - **Owner (2026-10-01 ~21:10 UTC+3): "at 1080p it is not dark, God of War
    is completely fine at 1080p."** This closes the earlier "dark overall"
    worry (19:15 report) for native 1080p: the darkening is only below 1080p
    (720p / FSR), as the darkening agent's readback numbers show. The
    `env.MADEIRA_LD_BOUNDS = 0` A/B at 1080p is no longer a darkening test,
    only a possible small GPU gain (perf doc 3.2 item 5). 1080p is the
    reference that must not regress in every experiment.
  - **Build 303 green** (run 36904068206, head 2292a4b, 2026-10-01 18:24
    UTC): notices "dxgi-src.dll built from DXMT a5e0cd3 with IDXGIFactory7 +
    EnumAdapterByLuid (1748992 bytes, exports = upstream's)", "the recipe
    reproduces upstream's dxgi.dll without the patch (9663 symbols ...)",
    "dxgi-src.dll present". main fast-forwarded to 2292a4b; its push run 304
    (workflow changed) cancelled.
  - **GoT "objelerdeki sıkıntı" = smoke squares (agent, 2026-10-01; docs/got-corruption.md).**
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
    Merged as c6b98b1 (agent commits 8b7552a, 69cdf9c); host checks after
    the merge: got-diagnostics, dxgi-factory7, patch chain, catalog PASS.
    Cost: native ABI change (IPA, not a pack); GoT re-converts its shaders
    once on the first launch of the next build.
  - **GTA V on build 303 (owner, logs PlayGTAV.exe 2026-10-01 21:25:32
    without and 21:27:54 with `env.MADEIRA_DXGI_SRC = 1`, both with "Report
    an NVIDIA GPU"; two screenshots).** The game's error box is now DRAWN
    and the game-mode input wake works (`[game-input] ... hwnd=0x10028`).
    - Without the switch: Factory7 unknown -> **ERR_SYS_SYSREQ_GPU** ("Your
      video card does not meet the system requirements", OK / Cancel).
    - **With the switch: Factory7 works** (`[dxgi-src] ... first factory
      request a4966eed...`, `RegisterAdaptersChangedEvent: cookie 1`), the
      game creates D3D12 devices on the REAL adapter (`D3D12CreateDevice(
      adapter=0000007016B3F8E0 ...)` 5374, again at 7331), runs its format
      support census (many "texture format N has no Metal mapping": RGB32,
      YUV, palette formats -- expected), then asks NVAPI: GetFullName ("RTX
      4090"), GetGpuCoreCount -104, GetAllClockFrequencies -104, and
      **`NvAPI_GPU_GetPhysicalFrameBufferSize` / `GetVirtualFrameBufferSize`
      -> "err: nvapi: function ... not implemented"**; the very next line is
      `destroyed Device` and the box **ERR_GFX_D3D_NOD3D12** ("Failed to
      initialize DirectX 12 adapter"). No CheckFeatureSupport refusal in the
      log. Conclusion: the VRAM query is the next blocker.
    - **Fix (this commit): `tools/patch-nvapi-gpu-info.py`** in
      `tools/build-dxmt-nvapi.sh` (after patch-nvapi-strings, before the
      trace): both frame-buffer sizes in KB = the Metal device's
      recommendedMaxWorkingSetSize (= DXGI DedicatedVideoMemory), logged as
      `[nvapi] NvAPI_GPU_GetPhysicalFrameBufferSize -> 0 N KB`;
      GetGpuCoreCount -> 16384 (the RTX 4090 / AD102 this NVAPI already
      names). GoT never calls these three (its 20:26 log). Verified here:
      `tools/build-dxmt-nvapi.sh` builds and links nvapi64.dll with the
      Linux llvm-mingw 20260421 (the dxgi agent's hybrid toolchain);
      `tests/host/check-nvapi-trace.py` extended (order, idempotence, the
      two cases, core count still traced) PASS, also with the arm64ec
      compile step. Open: the NVAPI name (RTX 4090) and DXGI / registry
      identity (RTX 3060, 10de:2544) still disagree; ClockFrequencies stays
      NOT_SUPPORTED; D3DKMTEnumAdapters2 lists 0 adapters.
  - **Build 306 dispatched** (run 36907666595, head 98ef76f): 303 + GoT
    smoke-square diagnostics + NVAPI frame-buffer sizes; it supersedes the
    running 305 (d50c20f, concurrency cancel).
  - **Owner's standing permission (2026-10-01):** start multiple agents
    (subagents) whenever they help solve a problem or reach success faster;
    no need to ask first ("hata çözmek için gerektiğinde çoklu ajan
    başlatabilirsin ... benim söylememi bekleme").

### DualSense / DirectInput (second agent)

* **2026-10-01 (Claude, second agent, worktree branch
  `worktree-agent-a508c6faab1405d26`, local only: not pushed, no CI run).**
  Phase 1 done in code, not device-tested. Feature doc: `docs/CONTROLLERS.md`
  "Player 1 as a HID controller (DualSense, DirectInput)".
  - **The stopped agent's WIP `7da53e7` was reviewed and kept.** Verdict: the
    design is sound and fits how Wine runs on iOS; one real bug, a few small
    ones. Taken over by cherry-picking it unchanged (commit 4e09bc4, its
    app/ and build/ trees identical to 7da53e7), fixes in the next commit.
  - **Why the pad lives in the wineserver, not winebus.sys** (checked in the
    code): desktop Wine reaches hid.dll through plugplay/winedevice loading
    winebus/winehid/hidclass/hidparse. Here CI builds no winedevice.exe or
    plugplay.exe (.gitignore), the IPA ships no .sys, the prefix template has
    the winebus/winehid/PlugPlay services disabled because winedevice
    "wedges on iOS" (patches/wine-rpcss-scm-bootstrap.patch), a library game
    session starts no SCM, and nsiproxy.sys / mountmgr.sys were already
    replaced the same way (nsi_unixlib_ios.c, ios_create_drive_symlinks). The
    wineserver runs in the app's task, so it reads the app's snapshot
    directly, and serves `\Device\MadeiraHidPad0` like ConDrv/named pipes.
  - **How it works:** the app decides at session start
    (`GamepadInput.beginPadSession`, before the wineserver starts) from
    `env.MADEIRA_PAD_MODE` (game file > madeira.cfg; unset = XInput) and
    exports `MADEIRA_HIDPAD=dualsense|generic`. The wineserver
    (`build/wineserver/hidpad_ios.c`) creates the device + `\??\HID#...` link
    and answers ReadFile/WriteFile and the hidclass ioctls (preparsed data from
    Wine's own hidparse.sys compiled in, `build/hidpad/hidparse_ios.c`);
    ntdll's first process (`server_ios.c ios_hidpad_publish`) writes the
    volatile setupapi registry entries. Reports come from a second snapshot
    (`struct winios_hidpad`, WiniosGamepad.[ch]); the XInput snapshot and
    `driver_ios.c` are untouched. XInput mode creates nothing (no device, no
    registry key, no extra log line from native code).
  - **XInput in HID mode:** player 1 leaves XInput (a DualSense on Windows is
    not an XInput pad), so God of War, which reads XInput and libScePad, sees
    one controller; players 2-4 stay XInput; Wine's xinput only adopts
    WINEXINPUT devices, never this one; `env.MADEIRA_HIDPAD_XINPUT = 1` keeps
    both views. The opt-in joystick_ios DirectInput pad (MADEIRA_DINPUT_PAD)
    reads XInput slot 0 and so disappears for player 1 in HID mode.
  - **Fixes to the WIP (ml2105):** (1) registry: Wine 11 keys are named
    objects and one NtCreateKey over a missing parent fails
    (server/registry.c key_lookup_name), so the WIP's single call never
    created `Enum\HID\VID_054C&PID_0CE6&MI_03\...` and setupapi would have
    skipped the pad entirely -> keys are now created level by level; (2)
    ntdll publishes only for the `\??` link the wineserver really made (a
    hand-set env.MADEIRA_HIDPAD in madeira.cfg is exported after the
    wineserver started and could have advertised a device that does not
    exist); (3) DualSense product string "DualSense Wireless Controller" (the
    WIP had the DualShock 4's "Wireless Controller"); (4) the pad's file
    objects close like named-pipe ends (`async_close_obj_handle`), and a
    failed `\??` link no longer reaches `release_object(NULL)`; (5) Wine's
    debug-format warnings silenced in hidparse_ios.c; (6) Session menu >
    Controller (under CPU) shows the effective mode (game file, else
    madeira.cfg), says **Live in this session** / **Needs a relaunch**, and
    keeps an explicit `xinput` in the game file when madeira.cfg sets HID
    for every game.
  - **Evidence (local, Linux host):** `WINE_SRC=<wine 4f5b197>
    python3 tests/host/check-hidpad.py` PASS with clang and gcc: both
    descriptors through the pinned Wine hidparse.sys + hid.dll hidp.c, every
    button/axis/hat/touch/battery/sensor field, feature and output reports,
    the transport, and the registry block extracted from server_ios.c against
    a fake registry with Wine 11's parent rule (the WIP's version of that
    block fails it: "(3/4 keys)"). The DualSense descriptor is byte-identical
    (273 bytes) to github.com/nondebug/dualsense report-descriptor-usb.txt;
    report/feature/output offsets match Linux hid-playstation.c and SDL's
    SDL_hidapi_ps5.c (both master, 2026-10-01). hidpad_ios.c and
    hidparse_ios.c compile warning-free against the pinned wine/server
    headers with CI's forced includes; their undefined symbols all exist in
    libwineserver.a / the app. ConfigCatalog.generated.swift equals what
    gen-config-catalog.py produces over the pinned submodules (the same
    method reproduces the committed catalog byte for byte). check-gamepad,
    check-library-sections, check-launch-routing pass. **Not checked:** the
    Swift (no swiftc here; read by eye against the iOS SDK APIs),
    main_ios.c (needs the iOS SDK), anything on device.
  - **Build:** no workflow change. `build/wineserver/build.sh` compiles the
    two new objects into libwineserver.a; ntdll compiles server_ios.c in
    place. Native code changed -> needs an IPA build, not a pack.
  - **Device test (owner):** IPA with this; God of War's game sheet >
    "madeira-bcd: controller" > DirectInput / HID (or Session menu >
    Controller, then quit Madeira and start again); DualSense paired before
    the start. Log should show `[hid-pad] ml2100 session mode=hid
    source=game kind=dualsense pad=DualSense... xinput-slot0=off`, `[hid-pad]
    ml2101 device dualsense 054c:0ce6 "DualSense Wireless Controller" input
    64 output 48 feature 64 bytes, preparsed ...`, `[hid-pad] ml2102
    dualsense 054C:0CE6 registered (4/4 keys) ...`, then `ml2101 open #1`,
    `feature report 0x5/0x9/0x20 read`, `first input report: 64 bytes`. In
    game: PlayStation prompts, sticks/triggers/buttons/d-pad/touchpad click.
    A DirectInput-only game: its controller list shows "DualSense Wireless
    Controller". Back to XInput: the same picker; nothing of the above is
    logged then except `ml2100 session mode=xinput`.
  - **Open:** device test. Phase 2: output reports are parsed into
    `winios_hidpad_get_output` (rumble pair, both trigger effect blocks, light
    bar, player LEDs, mic LED) but nothing applies them on iOS yet.
    **Scope, honestly (upstream's author asked "will the iPhone let you send
    haptics to the DualSense? macOS lets you access the controller entirely
    over USB; iOS abstracts everything"):** iOS gives an app no HID reports,
    no USB, no audio channel, no speaker/mic -- only GameController:
    GCDualSenseGamepad state, GCDualSenseAdaptiveTrigger modes, GCDeviceLight,
    GCController.playerIndex (4 LED patterns), GCMotion, and CoreHaptics via
    GCDeviceHaptics. So phase 1 (a synthesized DualSense for libScePad and
    DirectInput, input only) is the core value; phase 2 can only map the
    game's output reports best effort: the rumble pair -> CoreHaptics
    (left/right handle engines), trigger effects -> the closest
    GCDualSenseAdaptiveTrigger mode, light bar -> GCDeviceLight, player LEDs
    -> playerIndex. Cannot be reproduced: audio-based ("advanced") haptics,
    which PC games stream to the pad's USB audio interface (the virtual pad
    has none, so such a game falls back to rumble or nothing), speaker,
    headset, microphone and mic LED, arbitrary LED patterns, light bar
    brightness, trigger parameters Apple's modes lack. Phase 3: touch
    coordinates (touchpadPrimary/Secondary; finger-up is not reported
    directly) and GCMotion gyro/accel (axes and signs need a device). Also
    open: WM_INPUT for this pad (the raw input list shows it, no reports are
    sent), the PS button reaches the game only when iOS does not keep the
    Home button (unchanged, as XInput's Guide), GameController has no mute
    button, the report counter is per device (two readers each see every
    other value).
  - **Repository layout:** main has since merged upstream's reorganisation
    (build/host-tests -> tests/host, research/dxmt -> dxmt, ...); the new
    host test is therefore already at `tests/host/check-hidpad.py` (it finds
    the repo root two levels up either way). After merging, rerun
    `build/tools/gen-config-catalog.py --check` (the catalog's source paths
    moved on main) and regenerate if it reports stale.

---

## 1. What this repository is

`bahacan16/madeira-bcd` is a personal fork of `willfaust/Madeira`: Wine + FEX
(x86-64 JIT, ARM64EC) + DXMT (D3D11/D3D9 over Metal) + `madeira_d3d12` (a D3D12
runtime over Metal that converts DXIL with Apple's Metal Shader Converter and
DXBC with DXMT's airconv) packaged as an iOS app. The owner runs Windows games
on an **iPhone 17 Pro Max, iOS 27.0**, sideloaded with Feather. Personal use
only; the bundle id stays `com.willfaust.mythicemu`.

Since build 222 (2026-09-29) the fork follows **upstream `willfaust/Madeira`
main** and its submodule pins (wine `daa17d0`, FEX `2838f3b`, DXMT `a5e0cd3`,
`research/madeira-dock`), with this fork's own work re-applied on top. The
earlier 125hz PRs (#28 WoW64 + DXMT D3D9 on `125hz/wine pr/wow64-core` and
`125hz/dxmt pr/d3d9`; #29 named touch layouts) were replaced by upstream's
own WoW64, D3D9 import and touch presets. What that switch dropped until it
lands upstream: 125hz's fastsync, fs caches and networking work in wine (125hz
is re-upstreaming them as `pr/fastsync-opt-in`, `pr/async-apc-requeue`,
`pr/image-map-notify-guard`). The pre-switch tree is the local branch
`backup/pre-upstream-switch` = commit `563ac69` on the dev branch history.

## 2. Working conventions the owner expects

* **Reply in Turkish.** Owner's clock is UTC+3.
* Work autonomously: diagnose from the log, fix, build, hand over an IPA link.
  The owner dislikes being asked things the agent can decide itself.
* The owner explicitly authorized **automatically starting this workflow after
  every crash/error report** (2026-09-27). Do not stop after pushing a fix;
  dispatch the development-branch workflow, inspect its result, and hand over
  the IPA run/artifact link. Keep this handoff append-only in substance so
  Claude and Codex can alternate without losing earlier findings.
* **Build monitoring preference (owner, 2026-09-27):** After dispatch, verify
  that the run started, then check its status **once about 10 minutes later**.
  Do not poll every step or send running-status screenshots; those wasted
  tokens during build 186. If still running, check again at a sensible longer
  interval, and report the final result and artifact link. Send a screenshot
  only when the owner asks for one.
* Develop on branch **`claude/madeira-bcd-repo-ymg5cb`**, push there.
* Build: dispatch `.github/workflows/build-ipa.yml` on that branch
  (workflow_dispatch). When it is green, fast-forward `main`
  (`git push origin <sha>:main`); if that starts an automatic push build on
  `main`, cancel it (it is a duplicate).
* Version = `0.1.<run_number>` (Info.plist stamped in CI). The artifact is
  `madeira-0.1.<N>-unsigned-ipa`; link format
  `https://github.com/bahacan16/madeira-bcd/actions/runs/<run id>`.
  Downloading artifacts needs a signed-in GitHub account (GitHub rule).
* CI failures: read annotations with
  `curl -s https://api.github.com/repos/bahacan16/madeira-bcd/check-runs/<job id>/annotations`;
  full logs via the Actions UI / API job logs.
* Commit messages: say what was wrong, the evidence, and the fix (see
  `git log`). Keep `docs/madeira-bcd.md` updated for every change.
* **Update packs (since build 215) -- prefer them to a new IPA.** A change
  confined to the D3D12 runtime's PE source (`research/madeira-d3d12/src/pe`)
  does NOT need an IPA: pushing it to the dev branch runs
  `.github/workflows/build-pack.yml` (a few minutes), which publishes
  `madeira-pack-<N>.zip` + `index.json` on the public prerelease **`packs`**.
  The owner taps Settings > Updates (or the home banner) and the next game
  start uses it. Tell the owner "pack N", not an IPA link, for such fixes.
  A pack installs only over an app whose `MadeiraNativeABI` (Info.plist)
  equals the pack's `native_abi` (`tools/native-abi.sh`: app/, build/, DXMT,
  the conversion service, patch scripts, wine/FEX commits). Anything native
  (Swift/ObjC, ntdll-unix, winemetal unix, madeira_cfg.h, DXMT patches) still
  needs the IPA build -- and after it, packs are built against the new ABI.
  If a workflow change alters the native build, bump `EPOCH` in
  `tools/native-abi.sh`. The hash is over git blobs, so ANY edit to a native
  file (a comment too) makes packs built afterwards refuse the installed app:
  batch native edits into the next IPA rather than touching them between
  builds. Check with `tools/native-abi.sh` against the app's value
  (Settings > Updates shows it). The `packs` release holds only DLLs built from this
  repository (never an IPA, Apple's converter or Microsoft's runtime).
* **Per-game config:** Settings sheet of a game > "Advanced: this game's
  config" edits `Application Support/GameConfigs/<hash>.cfg` (madeira.cfg
  syntax). Exported as `MADEIRA_CFG_GAME`; `madeira_cfg_get` lets its keys win
  over madeira.cfg and its `env.*` lines are exported last. Use it to ask the
  owner to A/B a switch for one game without any build.
* A 12-hour "upstream sync" routine runs on the Claude side (merge
  `willfaust/Madeira` main into the dev branch keeping this fork's additions,
  build, report). By hand: `git fetch upstream main` (remote =
  willfaust/Madeira), merge, keep this fork's additions, build, fast-forward
  main. Since build 222 upstream's side (and its submodule pins) wins where it
  replaced something we carried.

## 2b. Over-the-air install (owner's decision 2026-09-30)

* CI step "Sign for OTA install (private bucket)" runs
  `tools/sign-and-publish-ota.sh` after the unsigned IPA is packaged
  (continue-on-error; skips itself when a secret is missing).
* The owner's signing files live ONLY in the owner's **private** Backblaze B2
  bucket `Github-BCD` (root: `Development.p12`, `Development.mobileprovision`).
  Repository secrets: `B2_KEY_ID` (the keyID, not the key name), `B2_APP_KEY`,
  `B2_S3_ENDPOINT` (`s3.eu-central-003.backblazeb2.com`), `B2_SIGN_BUCKET`
  (`Github-BCD`), `SIGN_P12_PASSWORD`. The key is limited to that bucket.
* Output: `ota/Madeira-<ver>.ipa` + `ota/manifest-<ver>.plist` (last 10 kept;
  the cleanup only works from the build after 262, see section 0)
  and `kurulum-<ver>.html` at the bucket root with a "Yükle" button (owner
  asked for the version in the name, 2026-09-30; the last 10 are kept); links
  are 7-day pre-signed URLs. The owner opens the newest `kurulum-<ver>.html`
  from the B2 panel/app; tapping "Yükle" makes the iPhone download
  `ota/Madeira-<ver>.ipa` straight from the same private bucket.
* **Nothing is public:** the repo and its Actions logs are public, so the
  script never prints a URL or key. A public/unlisted bucket was refused by the
  session's safety check (the IPA contains Apple's converter library and the
  owner's device-bound profile) -- do not reintroduce it.
* **E-mail delivery (added 2026-09-30, owner found the B2 login tedious and
  asked about Google Drive):** Drive cannot serve the OTA itself -- iOS's
  installer fetches the manifest/IPA without any login, so a Drive file would
  have to be shared publicly (refused above), and Drive answers large files
  (>100 MB) with an HTML virus-scan page instead of the bytes. Instead, when
  the secrets `OTA_MAIL_USER` (sending Gmail/Workspace address),
  `OTA_MAIL_APP_PASSWORD` (an app password, not the account password) and
  `OTA_MAIL_TO` exist, the script e-mails the owner a 7-day pre-signed link to
  `kurulum-<ver>.html` (smtp.gmail.com:587, STARTTLS); it opens in Safari with
  no login, "Yükle" installs. The address stays in secrets (public repo); the
  log only says "install link ... e-mailed". A mail failure is a warning only.
* **Cloudflare R2** (prepared 2026-09-30, owner switches 2026-10-01): with the
  four `R2_*` secrets the same script uses R2 instead of B2 (no egress fees;
  B2's free plan allows 1 GB of downloads a day, ~6 installs).
  In use since build 271 (2026-10-01): the four `R2_*` secrets exist, the
  signing files are at the R2 bucket root, the log says "private R2 bucket".
* **Storage budget** (owner, 2026-10-01: never past R2's 10 GB free tier):
  the whole bucket stays under `OTA_BUDGET_GB` (default 8) and at most 10
  builds; old builds are removed before the new upload, the log notice says
  how much is used.
* Signing keeps the IPA's own bundle ids (`com.willfaust.mythicemu`, extension
  `.MemoryHost`), like the owner's Feather install, so an OTA install updates
  the installed app in place. `SIGN_USE_PROFILE_BUNDLE_ID=1` would rename to
  the profile's App ID instead.

## 3. Hard rules (do not break)

* **Never commit Microsoft VC++ runtime DLLs** (`app/Madeira/x86_64-vcruntime/*.dll`
  is gitignored; CI fetches them).
* **Apple's Metal Shader Converter** installer lives ONLY as an asset of a
  **DRAFT** release tagged **`msc-private`** (`Metal_Shader_Converter_4.0_beta_2.pkg`).
  CI extracts headers + the iOS library at build time into gitignored
  `build/madeira-d3d12/msc-include/`. Never commit the pkg, headers or library,
  never publish that release. Since build 181 CI **fails** if the release is
  missing (build 180 silently shipped a stub: black screen in every D3D12 game).
* Do not publish IPAs as public releases without the owner's decision (the IPA
  contains Microsoft redistributables and Apple's converter library).
* Do not commit externally supplied binaries (exception already granted: the
  125hz PR #28/#29 DLLs).
* The owner's Ghost of Tsushima / Crysis copies are cracked (RUNE / Steam
  emulator). Fix Madeira-side bugs only; **do not help configure crack or
  Steam-emulator files** (e.g. `steam_api.ini`).
* A GitHub PAT was once pasted in chat; the owner was told to revoke it. Never
  use tokens from chat. The signing `.p12` (+password) and `.mobileprovision`
  must never be committed or printed. Since 2026-09-30 (owner's decision) CI
  uses them only from the private B2 bucket for OTA signing (section 2b);
  agents do not handle the files themselves.

## 4. Ghost of Tsushima (D3D12, Nixxes port) -- PAUSED 2026-09-29

### Where it stands (owner paused GoT on 2026-09-29; resume from here)
State: IPA 218 (native ABI 48a89bc6c3cadd93) + pack 6 (68e4735). Playable in
gameplay at ~35-45 FPS at 1280x720 with FSR3 Performance. Open items, in order:
1. **C++ exception fast-fail (0xC0000409), the main stability blocker.** It
   happens during loading and in gameplay (logs 09-28 18:53, 20:41; also
   builds 187 and 191). The stack is always the same: GhostOfTsushima+0x449681
   (recursive), +0x40a99d, VCRUNTIME140_1 frame handler, and the handler
   thunk +0xd15f0c ends in __fastfail. It is not the device list race
   (pack 5 did not change it). Hypothesis: during C++ exception dispatch
   through x64 frames under ARM64EC/FEX, the unwinder or dispatcher context
   (ControlPc / ImageBase / state) is wrong, so __CxxFrameHandler4 reaches
   terminate. Next step is native, so an IPA: log the DISPATCHER_CONTEXT of
   every frame for code e06d7363, and whether `_ThrowImageBase` is 0 (see
   "Build 191 results").
2. **Rendering corruption the owner calls "objelerdeki sıkıntı".** It must be
   re-checked with pack 6 in a session where F0 is NEVER used: every earlier
   observation after an F0 test was polluted (see "Pack 6"). If it remains,
   press CAP while it is on screen. The leading suspect is the velocity target
   (RG16F, NaN/Inf over the sky in older captures) feeding FSR3/TAA. FSR3
   Performance's jagged edges are expected (internal ~640x360); with FSR off
   the edges are clean but the corruption stays, and FPS drops a lot (GPU-bound
   at native 720p).
3. Performance: in steady gameplay the game's own CPU time under emulation
   dominates (~18 of ~25 ms). Our D3D12 layer costs 4-6 ms: encode 0.7,
   encoder open/end 1.8, the rest is the replay. async-submit=1 takes that
   off the game thread, but the worker sits at ~16 ms per frame; re-measure
   on a cool phone. F5 measured +2-3 FPS over F1 (owner, 09-28), which makes
   it a candidate per-game default.
4. Hitches of 50-550 ms are first-draw pipeline compiles (pso-lazy); the
   shader cache removes them on the next visit.

### Progress so far (each item is a commit; details in docs/madeira-bcd.md)
Save folder -> D3D12 use-after-free -> display config crash -> GPU driver info
(NVAPI entry points + a registry display adapter, "Report an NVIDIA GPU"
per-game switch) -> `GetAdapterLuid` -> `GetDeviceRemovedReason` -> DXBC
static samplers (black screen) -> intros + main menu work -> New Game OOM
(30k Metal libraries) fixed by lazy pipelines + shared libraries + a
persistent disk shader cache -> game reaches gameplay (~20-40 FPS) ->
**GPU timeout a few seconds into gameplay** (the remaining blocker).

### The GPU timeout (fixed in build 181, confirmed on device)
Every run: 2-5 s into gameplay FPS sinks from ~40 to ~20, then Metal ends a
command buffer with `MTLCommandBufferError` code 2 (timeout), ignores the queue,
and the game tears itself down (its workers then fault copying freed memory,
its crash handler `crs-handler.exe` crashes — both are consequences).
Found with the fault-attribution machinery (below): the kernel (DXIL hash
`34c565ac8322ab2a`, 3948 bytes, `Dispatch(221,1,1)`, 64 threads/group) is a
vertex-normal recompute. Each thread reads a `[first,last)` adjacency range
from a StructuredBuffer at its thread id and loops `until i == last`. The
dispatch is rounded up to the group size, so the extra threads read past the
buffer. D3D12 returns 0 there; the converter did not bounds-check
(`IRCompatibilityFlagBoundsCheck` was off), read garbage and looped forever.
**Build 181 converts with `IRCompatibilityFlagBoundsCheck`**
(`research/madeira-d3d12/src/unix/madeira_ir_unix.mm`; opt out with
`MADEIRA_IR_NO_BOUNDS_CHECK=1`). The shader-cache key changed, so the first
launch re-converts everything (the "Compiling shaders" screen takes a few
minutes and looks frozen — do not close it).

**Next step:** have the owner run build 181 (AVX on, "Report an NVIDIA GPU"
on, press Enter at the dark launcher, New Game) and check the log: there
should be no `GPU fault` line and FPS should stay flat.

### Build 181 result (log 2026-09-27 14:55, 800x600): the GPU timeout is GONE
No `GPU fault` line at all; the scene renders (banners, grass) at 50-60 FPS
before gameplay. The new wall is on the CPU: when gameplay starts,
`ExecuteCommandLists` per frame goes 25 ms -> 273 ms -> 2.3 s while the GPU
is 2-7 % busy (Metal HUD: "Detected high CPU encoding cost with encoders
spending an average of 100% of frame time encoding"; "Compiled Shaders 693 |
12.5 s"). Cause: lazy pipelines (`mad_pso_realize`) are compiled by Metal at
their first draw, on the submitting thread, one at a time, under one global
lock; the first gameplay seconds need hundreds. After ~2 s frames the game
stops itself at the same `int3` it uses for fatal errors (guest RIP ...9acd,
call chain ...b950 / ...63e5) — most likely its own hang watchdog.

**Build 183** (commit "build a batch's new pipelines in parallel"): a per-pipeline lock replaces the
global one, and before a batch is replayed the lazy pipelines its lists bind
are built on up to 4 threads (`mad_prebuild_lists`, madeira.cfg
`pso-parallel = 0` to disable; log line `pso-parallel: built N pipelines`).
Expected: the stall shrinks roughly by the core count. If frames still take
seconds, next steps (in order of payoff):
1. **Persist compiled pipelines across launches** with `MTLBinaryArchive`
   (or Metal 4 `MTL4Archive`): add winemetal calls to create/load an archive,
   add pipeline descriptors to it, serialize it next to the shader cache
   (`%LOCALAPPDATA%\Madeira\ShaderCache\<identity>\`), and pass it as
   `binaryArchives` when creating pipelines. Second launch then compiles
   nothing. Needs changes in `research/dxmt/src/winemetal` (done at build
   time through a `tools/patch-dxmt-*.py`, like the fault-info patch).
2. Start building a lazy pipeline in the background at `CreatePipelineState`
   time at low priority, capped by Metal memory (eager creation of all
   ~14k pipelines hit 5.1 GB and jetsam before; do not go back to that).

### Build 183 result (log 2026-09-27 15:34)
Main menu much smoother (ExecuteCommandLists ~2 ms/frame, 45-48 FPS; parallel
builds working: `pso-parallel: built 20..69 pipelines on 4 threads`). Gameplay
start still froze: presents stopped right after the first large prebuild
batches, then the game tore itself down (workers faulted on memory another
worker freed — the usual teardown symptom). Two problems visible in the log:
* each prebuild batch CREATED 3 Wine threads: every one costs an 8 MB stack
  (floored), a TEB and FEX thread state — a storm of `init_thread_stack` lines
  and failing 8 MB reserves (`[va-scan] FAILED ... size=0x800000`).
* the 64-bit high-band fallback only searched 0x7200000000..0x73ffff0000,
  which is already occupied on device (every `[wow-window] #N ... NOT placed`),
  and a 1 MB FEX allocation still got STATUS_NO_MEMORY.
Also note: this run had 16,968 shader-cache misses because the cache key
includes the madeira_d3d12 build stamp — every new build re-converts every
shader once (first launch after an update is slow; second launch is not).

**Build 184**: a persistent pool of 3 prebuild threads (created once), and the
high-band fallback searches everything above the 32-bit windows up to the
user-space limit (still bounded by a caller's limit_high). If gameplay still
freezes, check whether presents stop while `pso-parallel` batches run
(pipeline compile time) or with no batches (then it is something else: look
at the game's worker threads / waits).

### Build 184 result (log 2026-09-27 17:02): crash DURING "Compiling shaders" (97 %)
No GPU fault, no pipeline stall. The crash is the same memory race seen in
every earlier run, now clearly independent of the GPU: the view history shows
a 1 MB + 64 KB block (`0x110000`) CREATED by the main thread 69 s earlier and
DELETED by a JobWorker 4 ms before the main thread (or another worker) faults
memcpy'ing 1 MB out of it (source = block + 0x40). Same size and shape in
four runs. That is one thread releasing a buffer another is still reading —
on Windows the game waits for its jobs first, so a wait here returned early
or a signal arrived too soon. Prime suspect: Madeira's in-process fast path
for events/waits ("fastsync", `MADEIRA_FASTSYNC`, auto-enabled after 20k ops/10 s,
see `build/ntdll-unix` sync code).

**Build 185**: per-game switch "Safe thread sync (no fastsync)" in the game's
Launch options (sets `MADEIRA_FASTSYNC=0` for that launch). Test GoT with it ON.
If the race disappears, the bug is in fastsync (look for a wake that is
delivered before the waiter's condition is really satisfied, or a
`WaitForMultipleObjects(waitAll)` / auto-reset event edge case). If it still
crashes, add a watch: `vmwatch` in madeira.cfg cannot help (addresses differ
per run); instead log the guest call stack of the thread that frees a
0x110000 view (NtFreeVirtualMemory caller RIP) and of the reader.

### Build 185 attempted test (2026-09-27 18:21, log `GhostOfTsushima.exe-2026-09-27_18-21-33.txt`)
The game crashed again, but **this was not a fastsync-off test**: at log line
269 Wine says `[fastsync] ... mode=auto`, at line 15147 it says `AUTO-ENABLED`,
and subsequent `[perf]` lines count tens of thousands of fastsync hits. No
`[madeira-env]` line sets `MADEIRA_FASTSYNC`. The owner subsequently confirmed
that the per-game switch had not been enabled for this run.
`LaunchRequest.apply()` in `app/Madeira/HomeView.swift` does set the variable
to `0` when its saved
`safeSync` preference is true; the game's launched exe was the expected x64
`GhostOfTsushima.exe`, with AVX and NVIDIA reporting enabled. Re-check the
game's **Launch options > Safe thread sync (no fastsync)**, use **Save and play**
and confirm the next log says `[fastsync] ... mode=off` (the exact mode string
should be checked against the log). A fallback is `env.MADEIRA_FASTSYNC = 0`
in `Documents/madeira.cfg` for the experiment. Do not treat this run as
evidence for or against the fastsync hypothesis.

The original failure reproduced: a worker (tid `00f0`) deleted the
`0x706ed30000+0x110000` view **2 ms** before tid `00f8` read from
`0x706ed3c000` during a 1 MB copy (`c0000005`; `[fault-rgn]` lines
36299-36316). No new GPU timeout was logged. The process later ran the game
crash handler; its own faults are secondary. Next action is a true fastsync-off
run. If the same freed-while-read signature remains with `mode=off`, collect
the freeing and reading guest call stacks as proposed above.

### Build 185 valid fastsync-off test (2026-09-27 18:29, log `GhostOfTsushima.exe-2026-09-27_18-29-58.txt`)
The owner enabled the switch and got about **3–5 more seconds of gameplay**
before another crash (one run, so this is not established as an improvement).
Log line 273 says `[fastsync] ... mode=off (pre-ml952) peek=off`; all reported
`[perf]` fastsync hit/miss/peek counters remain zero. Thus fastsync was really
disabled, and disabling it alone did **not** prevent this crash. Do not
continue to treat the fastsync fast path as the sole cause.

At lines 36966–37076, the source address `0x70f0dd0040` belongs to a
`0x70f0dd0000+0x210000` Wine view created by tid `0024` about 8.6 s earlier
and **deleted by tid `00f8` 7–8 ms before the faults**. Threads `00ec`,
`00f0` and `0024` fault on reads from that source during 2 MB copies in
`ntdll.dll+0x64074` (different destinations). There was no new Metal command
buffer failure; the later `crs-handler.exe` faults are secondary. The log
proves a freed-while-read overlap, but does not yet prove whether the early
free is a game scheduling error, a different Madeira wait/signal problem,
or some other translation/VM behavior.

**Next diagnostic change (after this result):** `virtual_ios.c` captures the
release site on `NtFreeVirtualMemory(MEM_RELEASE)` for 1 MB+ guest-band views
and attaches it to the existing deletion-history record. On the next fault,
`[free-origin]` prints the native return address, FEX live and saved x64 RIP,
saved x64 RSP, and up to eight candidate return addresses within the main
exe (with RVAs) scanned from the saved guest stack. These are candidates,
not a verified unwind; compare them with the reader's existing `[callret]`
trace. The data prints only when a later fault overlaps the freed view.
Build and test this instrumented revision next; then identify the releasing
call site before changing scheduling or memory-lifetime semantics.
The diagnostic code and these notes were pushed together as commit
`6d758e544cffeff98ad8a7720b96690ec053cdc7` on the development branch.

**Build dispatch status (2026-09-27, Codex):** The owner authorized automatic
workflow dispatch after every error report, now recorded above. The GitHub
connector can push commits but does not expose `workflow_dispatch`; the
cloud-browser GitHub login reached the two-factor app-code step, then GitHub
returned “Your browser did something unexpected” after verification. A fresh
workflow tab remained signed out. No new workflow run or IPA has been created
yet; do **not** report build 186 as started. The development branch now includes
the diagnostic commit plus the handoff authorization note (`2e4de7f8`), while
`main` remains at the previous tested commit. Resume with an authenticated
GitHub Actions dispatch on `claude/madeira-bcd-repo-ymg5cb`, inspect the run,
and fast-forward `main` only after a successful build.

**Update 2026-09-27 18:53 (UTC+3):** The owner completed GitHub sign-in in the
cloud browser. Codex dispatched `build-ipa.yml` from
`claude/madeira-bcd-repo-ymg5cb` at commit
`0c925759891f7e63a2267faec2f63f63b34fbeb0`.
Workflow **#186**, run **36331180977**:
`https://github.com/bahacan16/madeira-bcd/actions/runs/36331180977`.
Initial status `in_progress`; await result and artifact before declaring an IPA
ready or advancing `main`.

**Build 186 result (2026-09-27 19:09 UTC+3): SUCCESS.** Run
`36331180977` completed successfully from commit `0c925759`; the `Archive
(unsigned)`, `Package unsigned IPA`, and artifact upload steps all passed.
Artifact **`madeira-0.1.186-unsigned-ipa`**, id `10935873381`, about 141 MB;
download it from the run page above while signed in to GitHub. This validates
compilation and packaging, **not** the on-device crash. The next device test
should retain AVX/NVIDIA settings and `Safe thread sync (no fastsync)` ON so
the new `[free-origin]` records can be compared with the build 185 mode-off
log. If it crashes, upload the complete session log. Compare the freed view,
release-site candidates and reader `[callret]` frames; do not infer an exact
caller from the stack scan alone.
After success, Codex fast-forwarded `main` to the development branch's
`1ec7af666a0cb4033c9ed51fb67045ea8ce129f8` documentation commit;
both refs matched. The final handoff update itself is documentation-only and
should also be fast-forwarded to `main`.

**About the Metal HUD suggestion "adopt MTL4Compiler"**: Metal 4
(iOS/macOS 26+) has `MTL4Compiler` (explicit compiler objects, async
compilation with QoS, `MTL4Archive`, flexible render pipeline states that
share compiled vertex/fragment code). Madeira's bridge (DXMT winemetal) is
written against the classic `MTLDevice newRenderPipelineState...` API and the
converter emits classic metallibs; moving to MTL4 means rewriting the
winemetal pipeline/command-buffer layer, a large job. The same benefits for
this problem (no main-thread compile stalls, reuse across launches) are
available with less risk via parallel builds (done) and `MTLBinaryArchive`
(item 1 above). The HUD's other hints ("high number of interleaved blit
encoders", "render passes with similar attachments") are performance notes,
not errors.

Note: `C:\madeira-cs\fault-shaders.txt` keeps hash 34c565ac8322ab2a, so every
launch logs that shader's bytecode once (harmless, ~8 log lines); delete the
file in the Wine prefix to stop it.

### Open issues, roughly in priority order (updated 2026-09-28 morning)
Build 203 was tested on the device (log `GhostOfTsushima.exe-2026-09-28_07-42-33.txt`):
the C++ fix was NOT applied (`[pc2fh] ... padding in use`), the water pipelines
failed at the vertex shader, the launcher stayed dark, the owner saw broken
rocks and occasional dark patches in the air. Build 204 fixes the first three
(see "Build 204" below); the rocks need a close-up screenshot.
1. **Verify 204 on the device** (`pso time (...)` lines say how much of
   "Compiling shaders" is Madeira's): `[pc2fh]` at start-up and no VCRUNTIME140_1
   crash after saving; `shader cache ON ... identity 'madeira_d3d12 bc1
   converter <hex>'` and mostly hits on the second launch; `[madeira-ir] MSC
   4.0.1 compatibility: position invariance on, strict NaN/Inf on, ...`;
   water: `DXIL tessellation: vs ...`, `[winemetal] DXIL tessellation pipeline
   OK`, `DXIL tessellation: N drawn` -- or the reason it stayed a placeholder.
2. **Remaining slight artefacts** (owner, after build 194): nature unknown until
   the screenshot. 198's flags are the best guess; if they persist, capture
   (CAP) a frame showing them.
3. **Performance**: 10-17 FPS in gameplay at 800x600. Frame 57-96 ms, GPU
   22-36 ms of it (33-60 % busy), ExecuteCommandLists 10-17 ms on the game's
   render thread, ~230 encoders a frame with a full fence chain (fence-chain
   1; mode 6 has a known flicker hole). Mostly the game's own x86 threads
   under FEX (TSO on, half barriers). Ideas: fewer useResource calls per draw
   (up to 64 + heaps), MTLBinaryArchive for pipelines, attachment store
   traffic (~500 MB a frame, 300-420 MB never read again).
4. **"Compiling shaders" on a warm cache**: ~650-700 stages/s (build 190 log,
   ~1.4 ms each) -- still one small file per shader plus ~11k Metal library
   creations. 197 halved the reads (one per hit). Build 203's `pso time (...)`
   lines split pipeline creation into conversion+cache, library creation and
   the rest; decide from them. If library creation dominates: create a plain
   pipeline's MTLLibrary/MTLFunction lazily in `mad_pso_realize` (the cache
   file is the backing store; D3D12 lets the app free its bytecode, so keep
   the cache key, never a pointer). If conversion dominates: one packed cache
   file with an index instead of ~30k files.
5. The launcher window stayed dark until Enter / gamepad X was pressed -- fixed
   in 204 (the direct-launch GDI overlay was never given its host layer).
6. `DXGIFactory::EnumAdapterByLuid` not implemented (Streamline only);
   non-occlusion queries resolve to zero; `ResolveQueryData` into GPU-only
   buffers is not delivered.
7. 32-bit games through WoW64: Crysis runs with small problems (not looked
   at yet); Crysis 3 (32-bit) exhausts the 4 GB guest window (advise Bin64 /
   lower settings).

## 5. Debugging toolkit built during this work

Log = the file the owner uploads (`GhostOfTsushima.exe-<date>.txt`). Useful greps:

| grep | meaning |
|---|---|
| `GPU fault encoders: code N` | failed command buffer; code 2 = timeout, 3/4 = page fault/ignored; `[FAULTED] C#<seq> <kernel> fn=...` names the encoder |
| `GPU fault dispatch C#` | bindings of the faulted dispatch (root params, descriptors resolved to resources, `RUNS PAST THE END`) |
| `[b64 <hash>]` | bytecode of a faulting compute shader, logged at the NEXT launch (also `C:\madeira-cs\fault_<hash>.dxil`) |
| `shader cache: N hits` / `shared shader libraries` | disk cache / library sharing |
| `currentAllocatedSize`, `[footprint]`, `[proc-mem]` | Metal memory and process footprint (limit 8192 MB) |
| `[fault-rgn]   history:` | who created/deleted the view at a faulting address (1 MB+ views) |
| `[stack-quarantine]` | a dead thread's stack was touched while quarantined |
| `[va-scan] FAILED ... STATUS_NO_MEMORY` | address-space exhaustion |
| `[wow-window] ... placed above them` | 64-bit views placed above the 32-bit slots |
| `skips by site` | draws/dispatches skipped (L<line> in madeira_d3d12.c) |

Disassembling a captured shader:
```
grep -a "^\[b64 <hash>\]" log.txt | sed 's/^\[b64 [0-9a-f]*\] //' | tr -d '\n' | base64 -d > s.dxil
pip install llvmlite
python3 tools/dxil-disasm.py s.dxil > s.ll
```

madeira.cfg keys added here: `shader-cache` (default 1), `pso-lazy` (1),
`gpu-fault-info` (1), `gpu-fault-skip` (1), `encoder-labels` (0),
`vmwatch = 0x<addr>` (existing). Env: `MADEIRA_IR_NO_BOUNDS_CHECK=1`.

Metal Shader Converter headers for reading (never commit): download the pkg
from the draft release through the API, unpack xar -> Payload (pbzx/cpio) ->
`usr/local/include/metal_irconverter{,_runtime}/`. Key facts learned there:
descriptor heap bind point 0, sampler heap 1, top-level argument buffer 2;
UAV counters are an R32Uint texture-buffer view in the descriptor's texture
id word with the element offset in metadata bits 32..39
(`IRRuntimeCreateAppendBufferView`); buffer metadata = size | texview offset
<<32 | typed<<63.

Local compile check of `madeira_d3d12` (no device needed): llvm-mingw
`arm64ec-w64-mingw32-clang -shared -O2 -Wall madeira_d3d12.c d3d12.def -I...
-lwinemetal -luuid -lole32` with an import lib generated from
`research/dxmt/src/winemetal` exports (gendef/dlltool). The Wine unix side
(`build/ntdll-unix/*_ios.c`) only compiles in CI (Darwin/Mach headers).

## 6. Where things live

* `research/madeira-d3d12/src/pe/madeira_d3d12.c` — the D3D12 runtime (PE,
  ARM64EC). Most GoT fixes are here.
* `research/madeira-d3d12/src/unix/madeira_ir_unix.mm` — shader conversion
  service (Metal Shader Converter / airconv), unix side.
* `research/dxmt` (submodule, 125hz fork) — winemetal bridge; patched at build
  time by `tools/patch-dxmt-*.py` (the submodule itself is not modified).
* `build/ntdll-unix/virtual_ios.c`, `thread_ios.c` — Wine VM/threads on iOS
  (address-space windows, swap tier, view history, stack quarantine).
* `build/win32u-unix/sysparams_ios.c` — display devices / virtual GPU registry.
* `app/Madeira/*.swift` — the app (library, per-game settings incl. AVX and
  "Report an NVIDIA GPU").
* `.github/workflows/build-ipa.yml` — the whole build.

### Build 186 (ChatGPT/Codex) and 187 (Claude), 2026-09-27 evening
* Build 185 with "Safe thread sync" ON (fastsync `mode=off`) still crashed the
  same way, so fastsync is NOT the cause (Codex's notes above).
* Build 186 (Codex) only added free-origin tracing (`[free-origin]` lines
  under `[fault-rgn] history`). Its device run crashed at ~80 % of "Compiling
  shaders" with a different signature: Metal's completion handler
  (`IOGPUMetalCommandBufferStorageDealloc` -> `objc_release`) released a
  corrupted object (`x0=0x10701`), and a Wine thread crashed in `objc_release`
  on the same value. Reading: the same freed-while-used race — the game keeps
  touching a block after it was released, the VA has meanwhile been given to
  Metal/malloc, and Metal's objects get scribbled on. No `[free-origin]`
  output in that run (no guest fault on a freed view).
* **Build 187 (mitigation, not a root-cause fix)**: DELAYED RELEASE in
  `NtFreeVirtualMemory` (`build/ntdll-unix/virtual_ios.c`, `ios_fd_*`): a
  whole-view MEM_RELEASE of a private 1-16 MB guest-band allocation returns
  success at once but the mapping stays committed for `MADEIRA_FREE_DELAY_MS`
  (default 2000; 0 = off), max 128 MB in flight, then is really released.
  Late readers find valid memory and nobody else gets that VA meanwhile.
  Log: `[free-delay] #N release of ... held for 2000 ms`.
  If GoT gets through gameplay with it, the underlying race (job refcount /
  wait ordering under FEX) is still worth finding with the free-origin trace
  (set `MADEIRA_FREE_DELAY_MS=0` in madeira.cfg `env.` to reproduce).

### Build 187 result (log 2026-09-27 20:20, 1024x768, Adaptive Power was on)
* **The freed-while-used crash is gone.** The whole opening scene played for
  ~3 minutes, horse riding and control hand-over worked, the owner played ~2
  minutes with the touchpad, opened the menu and saved. `[free-delay]` held
  8 releases (1-8 MB each). Footprint peaked at 7.34 GB (limit 8 GB).
* HUD: GPU 14-44 ms/frame, 10-32 FPS; Metal warns about many render passes
  with similar attachments, interleaved blit encoders and runtime pipeline
  compiles (1000-1600 pipelines compiled during play). The log's render pass
  report: `ended by: targets 298, clear 77, dispatch 370 ... attachment
  load+store ~14848 MB` per 600 lists -- merging passes is a real FPS lever.
* Black squares (fixed screen positions, ~64 px) and a green block pattern in
  the lower part of the image remain. Still unexplained; a Metal frame
  capture (Mac + Xcode) is the fastest way to name the pass.
* **New crash after the save**: main thread AV READ of 0x16694 in
  VCRUNTIME140_1 (x64, `__CxxFrameHandler4`): `mov r12d,[rax+rbx]` with
  rbx = ThrowInfo->pCatchableTypeArray RVA and rax = `_GetThrowImageBase()`
  = 0. So a C++ exception arrived with ThrowImageBase (parameter 3) = 0.
  The stale guest state had rax = 0x11fb3e6a0, a JIT-pool alias inside
  msvcp140.dll's pool copy -- i.e. the ThrowInfo pointer was probably a pool
  VA, which `RtlPcToFileHeader` cannot map to a module. (The later crash of
  thread 0x50 is crs-handler.exe, the game's crash reporter, reacting.)
  The PE ntdll (`app/Madeira/arm64ec-windows/ntdll.dll`) is a tracked
  upstream binary and is NOT compiled by CI, so `RtlPcToFileHeader` cannot be
  fixed there.
* **Build 188**: unix `NtRaiseException` (`build/ntdll-unix/thread_ios.c`)
  repairs 64-bit C++ throws (0xE06D7363, 4 parameters) before dispatch: a
  pool-alias ThrowInfo is mapped back to the PE VA and its module base is
  filled in; a base of 0 is filled from the owning MEM_IMAGE allocation.
  Log: `[cxx-throw] #N ThrowInfo ... base ... -> ...: <how>` (first 32) and
  `[cxx-throw] ok ...` for the first 4 normal throws. If the crash returns
  WITHOUT a `[cxx-throw] #` line, parameter 3 was fine and the vcruntime
  per-thread data (`_ThrowImageBase` in the FLS ptd) is the suspect instead.

### Build 189: contact sheets for the black squares (no Mac needed)
The owner will not have a Mac soon, so visual bugs must be diagnosed from the
phone. Build 189 adds CAP contact sheets (docs/madeira-bcd.md): press CAP in
the overlay while the black squares are visible; `Documents/capture/` then
holds `f<frame>_sheet00.png ...` (20 numbered thumbnails each) and
`f<frame>_sheets_index.txt`; the log has the same `[capture-sheet]` lines.
Ask the owner for the sheets (as images) plus the log. Reading them: find the
first thumbnail (in encoder order) where the squares appear, magenta = NaN/Inf.
If it is a `cs <hash>` thumbnail, that dispatch produced them: next step is
`capture-cs` / the fault-shader machinery on that hash (dump its DXIL with
`tools/dxil-disasm.py`). Build 189 also carries build 188's C++ throw repair.

### Build 190 capture result (log 2026-09-27 21:15, main menu, 800x600)
Contact sheets work (283 thumbnails, 15 sheets). Findings:
* The main depth-stencil (800x600 D32S8, "DepthTarget") is clean after the
  G-buffer passes (#249, enc#179408, depth 0..0.057) and has **14336 NaN
  texels in a regular grid of small squares** at the next pass (#252,
  enc#179423 `PsMain`, which does not write depth: `w0`). The stencil plane
  (#253) shows the same grid plus garbage blocks = the green block pattern.
  The black squares in `PsMain`'s output (#251) sit exactly on that grid.
  Between the two passes only compute dispatches run (cs_main 100x75x1,
  13x10x1, 1x1x1, 11 indirect, 1x16x16), none with a bounded texture UAV.
* The previous frame's HDR image (#148, RGBA16F, probably TAA history)
  carries the same NaN squares, so they also feed back frame to frame.
* The 5th G-buffer target (RG16F, dx34, likely velocity) is NaN/Inf over the
  whole sky (#167/#174/#202); its clear is not visible (clear-only passes
  are not captured).
* Hypothesis: memory aliasing. DEFAULT heaps are Metal placement heaps
  (ml1145, `heap-backing = 1`); GoT uses many RT/DS-only heaps (flags 0x84).
  A resource placed over the depth memory and written by one of those
  dispatches (or a copy) would corrupt it in a grid, since Metal's tiled
  layouts differ by format. Build 191 adds the alias report to prove or
  refute it: look at the `| r#N heapH +a..b, OVERLAPS: ...` tail of the
  depth's `[capture-sheet]` lines, then `[capture-uavbuf]` / `[capture-op]`
  for a writer of an overlapping resource. If depth overlaps nothing, the
  NaN depth is a second DepthTarget (compare r# of #249 and #252).
* The second CAP of build 190 hung the game: thumbnailing a BC1 texture
  (captured as a UAV target) read past its copy while holding the capture
  lock. Fixed in 191 (BC skipped, reads bounds-checked).

### Build 191 results (logs 2026-09-27 21:46 and 21:48)
* Run 1 died before the main menu with the SAME C++ exception crash as after
  the save in build 187 (AV READ of 0x16694 in VCRUNTIME140_1, handler
  GhostOfTsushima.exe+0xd15f0c). No `[cxx-throw]` line: build 188's repair in
  unix `NtRaiseException` is never reached, because ARM64EC
  `RtlRaiseException` (wine/dlls/ntdll/signal_arm64ec.c) dispatches in user
  mode unless `peb->BeingDebugged`; only the second chance goes to the
  syscall. The PE ntdll is a tracked binary, so the fix has to live somewhere
  else (open; needs a deeper look -- where does the zero ThrowImageBase come
  from: the record, or vcruntime's per-thread `_ThrowImageBase`?).
* Run 2: pressing CAP crashed in `mad_texel_rgb` (madeira_d3d12+0x19478,
  default case): the capture copy's Metal-allocated shared memory was not
  mapped any more (prot 0). Build 192 backs capture copies with our own
  VirtualAlloc memory (no-copy Metal buffer) and locks the list in
  `mad_capture_buffer` too.
* **The aliasing hypothesis is refuted**: not a single `[placed]` line --
  GoT never calls CreatePlacedResource; its heaps stay empty, the depth is a
  committed resource. New leading hypothesis: a compute UAV descriptor holds a
  texture resource id that now belongs to the depth texture (a stale id of a
  released texture, reused by Metal), so a dispatch writes into depth. Build
  192 logs `[capture-uavtex]` for every UAV texture id (bounded ranges and
  the first 64 of unbounded ones) that resolves to no live texture or to a
  render-target / depth texture.

### Build 192 result (log 2026-09-27 22:18): black squares ROOT CAUSE found
Two CAPs worked (no crash). Frame 2311: the depth r#465 is clean at
enc#197148 (`ps_Copy`) and has 14336 NaN at enc#197163; `[capture-op]` in
between: `copy texture r#465 -> ... r#241` (stencil plane to an 800x600 R8
texture) and `copy texture r#241 -> r#465 mip 0 slice 1` -- D3D12
subresource 1 of a one-layer D32S8 resource is the STENCIL PLANE, which
Madeira decoded as array slice 1, so the copy wrote past the texture over
its depth and stencil memory. Build 193 decodes planes and copies aspects
properly (docs/madeira-bcd.md "Depth-stencil planes in copies"). Also seen:
UAV descriptors holding texture ids that resolve to no live texture (0x6cdc..
0x6cde, many shaders) and cs 3bc86a8a91b059a4 u8 resolving to the depth
(probably unused table slots; watch after the fix).
* Longer play in the same build-192 run (log 2026-09-27 22:18, part 2): no
  crash, footprint peak 6.6 GB. When the owner switched apps, iOS refused the
  GPU work ("Insufficient Permission (to submit GPU work from background)",
  code 7); Madeira took that for a GPU fault and switched the fault
  diagnostics on for good (every compute dispatch in its own encoder = slower
  for the rest of the run). Build 194 ignores that error for diagnostics.

### Build 194 result (log 2026-09-27 22:49): black squares FIXED
Owner: ~90 % of the corruption gone, only slight artefacts left. The capture
shows no NaN in the depth any more; the stencil round trip runs as
`aspect copy r#465 stencil -> r#241 colour` and back. Remaining NaN: the
RG16F G-buffer target r#483 (likely velocity) is cleared BY THE GAME with a
NaN colour (`[capture-op] clear RT (-nan ...)`), so that one is intentional.
The C++ exception crash (VCRUNTIME140_1, AV READ of 0x16694) happened again
at the end of the run -- the next main task. Owner has been told to raise the
effort level for it.

### C++ exception crash: ROOT CAUSE and build 196 fix
Analysed with Microsoft's 14.44 runtime (msvc-runtime wheel from PyPI, only
for disassembly, never committed): the fault is `mov r12d,[rax+rbx]` at
VCRUNTIME140_1+0x17b4 in FH4's FindHandler, rax = `_GetThrowImageBase()` = 0.
FH4 copies the throw image base from ExceptionInformation[3] at entry. MS's
`_CxxThrowException` would have switched the magic to 0x01994000 (pure) on a
zero base, so the record came from WINE's builtin runtime: Madeira keeps
Wine's ARM64EC vcruntime140 + msvcp140 (WineProcessBridge.m exemptions) but
overlays MS vcruntime140_1/concrt140. At RVA 0x166a0 of the shipped
arm64ec-windows/msvcp140.dll sits a ThrowInfo whose CatchableTypeArray RVA is
0x16694 -- the fault address -- type `std::runtime_error`; build 187's stale
rax was exactly that ThrowInfo's pool alias. Wine code computes the pointer
PC-relative in its JIT-pool copy, RtlPcToFileHeader(pool VA) returns 0.
Build 196 patches RtlPcToFileHeader's pool copy to reverse-translate first
(`[pc2fh]` log line at start-up). (Run 195 was the automatic build of the
main push of build 194's commits -- same content as 194; the fix is 196.) The same crash hits every game that mixes
Wine's msvcp140 with MS's vcruntime140_1 and catches a Wine-thrown exception.
Verified offline against the shipped ntdll.dll with a harness (patch lands on
RVA 0x35ea0, trampoline at RVA 0x8ffc0, idempotent).

### Build 197: the shader cache survives new builds
Every build used to start the device's shader cache from nothing (its key
held the DLL's compile time), so each new build sat on "Compiling shaders"
while ~29,000 stages converted again, and a DXIL miss ran the converter
twice. Build 197 keys the cache by a converter identity the CI computes from
everything that can change a conversion (docs/madeira-bcd.md, "Persistent
shader cache") and converts a miss once. The first launch of 197 still
converts everything (new identity); from then on a build that does not touch
the converter, DXMT's airconv, LLVM or the MSC library starts with a warm
cache. Log: `shader cache ON: ... identity 'madeira_d3d12 bc1 converter
<16 hex>' (vsps-fill 1, no-bounds-check 0, ags-roundtrip 0; ...)`; the
`shader cache: N hits, M misses` lines should show almost only hits on the
second launch.

### Build 198: converter flags for the remaining slight artefacts
Build 194's remaining artefacts are "slight" (screenshot pending). Two MSC
defaults differ from D3D12 in ways that produce exactly that kind of damage,
and the build-194 capture shows the game depends on both: ~350 draws a frame
redraw geometry with depth test EQUAL (D3D12 func 3, `dtest=1/func3/w0` in
`[draw-dump]`: cloth, moving objects, hair) -- without position invariance
Metal may compute those positions differently from the depth pre-pass --
and the game clears its RG16F velocity target to NaN on purpose, while MSC
4.0 optimises on the assumption that no value is NaN. Build 198 converts
with position invariance, strict NaN/Inf and sampler LOD bias
(docs/madeira-bcd.md). Each is a madeira.cfg switch (`msc-position-invariance`,
`msc-strict-nan`, `msc-sampler-lod-bias` = 0) for an A/B run; each switch
change re-converts every shader once. If the artefacts are gone but FPS
dropped, try `msc-strict-nan = 0` first (the likely costliest).

### Build 199: DXIL tessellation (the missing water)
Every run logged 12-16 "tessellation pipeline could not be built; returning a
placeholder whose draws are skipped" -- all of them Ghost of Tsushima's WATER
pipelines (`ls_Main_techWaterBlend`, `ps_Main_techWaterMain`,
`ps_WaterHeight_techWaterHeight`): DXIL hull+domain shaders, and the runtime
only had DXMT's emulation for DXBC ones. Build 199 builds them through the
Metal Shader Converter's own tessellation emulation (docs/madeira-bcd.md). Not
testable off the device: check the log for `DXIL tessellation: vs ...` (pipeline
converted), `[winemetal] DXIL tessellation pipeline OK` (Metal accepted it) or
`... REFUSED` / `Metal refused it` (with the reason), and `DXIL tessellation:
N drawn` in the ml1050 lines. If water scenes misbehave (GPU fault, hang),
`dxil-tess = 0` in madeira.cfg restores the placeholders. The workflow now
FAILS when madeira_d3d12.dll does not build (it used to ship upstream's old
tracked DLL and stay green).

### Build 201: housekeeping on the phone's storage
* ml931 wrote the first 400 compute shaders of every launch to
  `C:\madeira-cs\cs_<pipeline pointer>_<size>.dxil`; the pointer differs per
  run, so every launch added up to ~16 MB that nothing removed. Now opt-in
  (`cs-dump = 1`); the old dumps are deleted in the background (log: `removed
  N old compute-shader dumps`).
* The unix DXBC cache (`Documents/shadercache/*.mdsc`) got a fresh set per
  build and never lost the old ones; entries of earlier builds are removed
  once per build (log: `DXBC shader cache: removed N entries`).

### Builds 228-234: God of War hangs at start (presents 0), 2026-09-29/30
Tried and ruled out one by one on the device (each a separate build): madsync
off, 125hz's early JIT pool (6c944a6: upstream's placement again),
swap-min-kb, 125hz's decommit_pages (0046bce). Upstream's own build of the
same game was never tested here.
* Build 230 (2f8a0f4): the 2 s watchdog prints `[guest-stk]` lines for a
  thread parked in a syscall (TEB+0x378 syscall frame, fp chain, stack scan,
  JIT addresses reverse-mapped to module+offset). FEX offsets are symbolized
  with `llvm-nm -n -C` of the SHIPPED xtajit64.dll (RVA = addr - 0x180000000);
  since build 231 the shipped module is a CI rebuild, so the committed DLL's
  symbols are off by a few hundred bytes after Module.cpp.
* Build 231 (3705656, tools/patch-fex-ios-mapview-selfshared.py): guessed a
  self-wait on CodeInvalidationMutex in NotifyMapViewOfSection. Its log line
  (`[img-map] madeira-bcd`) never appeared; still hangs. The patch is kept
  (harmless).
* The build 230 stack, symbolized properly, is a self-wait on
  InvalidationTracker::IntervalsLock (std::shared_mutex, not recursive):
  HandleMemoryProtectionNotification holds it and logs `[iOS-xrem]` -> the
  log line grows FEX's heap (rpmalloc heap_get_page_generic) -> VirtualAlloc
  -> NotifyMemoryAlloc -> HandleMemoryProtectionNotification -> the same
  lock. Build 234 (840d90f, tools/patch-fex-ios-intervals-reentry.py; run 233
  was cancelled by mistake): the
  lock remembers its exclusive owner (TPIDRRO_EL0 on iOS); the memory
  notifications return at once on that thread and are counted
  (`[iv-reentry]` from HandleImageMap). Device test pending; then madsync and
  swap-min-kb back on for GoW one at a time.
* Build 234 on the device (logs 2026-09-30 08:57 and 08:58): the hang is
  gone. GoW now gets past imm32, loads concrt140/vcruntime140_1, starts its
  job-manager threads, initialises d3d11/dxgi (video budget, the 1368 MB and
  1026 MB reservations) and then faults the same way both times: guest code
  reads 0x40 (host LDAPR x27,[x6], x6 = 0x40; State.RIP 0x14002c4e0, callret
  [0] 0x14017d7a2, [1] 0x14002c4f0), host sp 0x71fe3c0000. The pre-switch
  build (125hz, log 2026-09-29 13:48) passes the same point: the exe was
  relocated to 0x15f210000 there, the 2 MB commit in the 1026 MB reservation
  was swap-backed (swap-min-kb), and crs-client.dll loaded next. Build 236
  logs every register, 256 bytes of host code before the fault
  ([fault-full], [fault-host]) and the guest bytes of the two innermost
  frames and their direct-call targets ([guest-fn]).
* Build 236 (log 2026-09-30 09:28) names it. A static constructor
  (0x14002c4e0, from the CRT's initterm at 0x140664xxx) builds a global at
  0x1427d27f0 with ctor 0x14017d750, which allocates 0x1000 bytes through
  the thread's current allocator: GoW.exe's own TLS block (TLS[0]) holds an
  index at +0xc and a table at +0xf0; the index is negative or the entry is
  0, so the allocator is NULL. 0x14040bf10 then finds TLS[0]+0x18 == 0 too
  (the other path) and reads NULL->0x40. The TLS setup order is identical
  in the pre-switch log that passes this point, so an earlier initializer
  took another path. Only visible difference at that point: the 2 MB commit
  at the start of the 1026 MB reservation was swap-backed there
  (swap-min-kb 1024) and is plain memory now. Next test: swap-min-kb = 1024
  back in GoW's config.
  Tested (log 09:32, build 236 with swap-min-kb = 1024): the commit is
  swap-backed again and the fault is unchanged -- not the swap tier. Build
  237 prints the thread's TLS[0] block and the image's TLS template at the
  first unhandled fault ([fault-tls]).
* Build 237 (log 09:53): GoW.exe's TLS template has the allocator-stack
  index at +0xc = -1 (empty); the main thread's block has +0xc = 0 and the
  table at +0xf0 holds [0] = 0, [1] = 0x7158890000 (the 1026 MB arena from
  jumbo#2). So the arena was pushed one slot too high, or something pushed
  NULL first, or +0xc was reset to 0 before the push (a 64-bit store to +0x8
  would do that). Other changes vs the template: +0x28 = 0x14506ce60,
  +0x58 low dword 0x80000000 -> 0x80000005. Finding the writers needs the
  code: GoW.exe itself (the owner's copy, analysis only, never committed).
* GoW.exe (owner's copy, kept out of the repo) disassembled: the allocator
  stack is push `idx = movsxd [tls+0xc]; [tls+0xc] = idx+1;
  [tls+0xf0 + 8*idx + 8] = heap` (14 inlined sites, e.g. 0x14040a8f0),
  pop `[tls+0xc] = idx-1`, and one restore (0x14040b2f0) that zeroes the
  table above the restored count; nothing else stores into the table. The
  memory init at 0x14040a8a3 pushes heap A (an object in .data at
  0x1426d18b0 + n*0x238, never NULL) right after the 1368 MB VirtualAlloc,
  then the 1026 MB arena (0x14040aa2f -> 0x1404ad5c0), then pops once. The
  observed state (index 0, table[0] 0, table[1] arena) is what you get if the
  first push, the one with index -1, never reached table[0]. No module has an
  unslotted static TLS (checked every DLL the log loads). Build 238 prints
  the stack at each of the first four jumbo reservations ([jumbo-tls]):
  jumbo#1 is heap A's VirtualAlloc (before the push), jumbo#2 the arena
  (after it).
* Build 238 (log 10:28): [jumbo-tls] #1 (before the game's first push)
  already reads index 0, and #2 (right after the push of heap A into
  table[1]) reads index 0 again; the arena push then overwrote A. So
  something outside the game zeroes TLS[0]+0x8..+0xf. It is FEX:
  xtajit64's own TLS template (0x30 bytes) holds `thread_local IRCapRIP`
  (PassManager.cpp, ml623 IR capture) at offset 8, Core.cpp clears it at the
  start of every block compile, and in the ARM64EC module that implicit-TLS
  access lands in the executable's TLS[0] block (implicit TLS is banned in
  xtajit64 for this reason; the WOW64 module already uses an atomic). Build
  239: tools/patch-fex-ios-ircap-tls.py makes it an atomic in the ARM64EC
  module as well. The other xtajit64 thread_local (AllocWatch's Anchor, +0x10)
  only has its address taken.
* Build 239 on the device (logs 10:49, 10:50, 10:51): past the allocator
  fault; Metal HUD up, the Sony Interactive Entertainment intro video plays
  for about a second, then it stops. Two of three runs: the unaligned
  backpatch race. Several video/decode threads run the same block; the Mach
  exception server rewrites LDAPR/STLR -> LDR/STR (+ half-barrier) for the
  first fault, then reads the next thread's (already queued) alignment fault
  with the plain form in place, matches nothing and sends it on as unhandled
  (`ldr x8,[x27,xzr]` / `str xzr,[x6,xzr]`, kr=0x101, same pc, x18 differs).
  Build 240: kr == EXC_ARM_DA_ALIGN on a rewritten form whose barrier slot is
  in place is re-run (pc for loads, pc-4 for stores) ([mach_exc]
  UNALIGNED-REPATCHED). Third run: FEX native code with x18 = 0 read
  TEB->TlsSlots[1] (addr 0x1488, pc libarm64ecfex+0x12f908) -- the iOS x18
  problem in FEX's TlsGetValue shim (Source/Windows/Common/WinAPI/Alloc.cpp,
  GetCurrentTEB() = NtCurrentTeb() = x18). Build 241 (240 superseded while
  running): tools/patch-fex-ios-teb-tsd.py makes the ARM64EC module's
  GetCurrentTEB() read the TEB from the TSD slot (TPIDRRO_EL0 +
  IosTebTsdOffset, as IOSLoadTEB does), x18 only as the fallback.
* Crysis64 (log 2026-09-30 11:05, build 239): the same fault as every run
  since 2026-09-26: CrySystem.dll+0x79788 reads through a pointer whose high
  32 bits are gone (0x264d004c; the full value 0x70264d055c sits in x1).
  CryEngine 2's 64-bit build relies on heap addresses below 4 GB, which
  Windows' bottom-up allocation gives it; iOS reserves the whole low 4 GB as
  __PAGEZERO, so no allocation can land there. Not fixable in the allocator;
  32-bit Crysis is the route.
* 32-bit Crysis (log 11:06): dies before any game code. aarch64 wow64.dll is
  relocated off its preferred base, the loader binds its IAT (.rdata page
  +0x33000), the read-only restore fails (`[vmem-denied] set_vprot failed
  ... protect=0x2`), so NtProtectVirtualMemory's IAT sync into the JIT-pool
  copy never runs; Wow64LdrpInitialize (+0x1b5fc) calls through the copy's
  unbound slot = hint/name RVA 0x34f06. Build 242: a refused read-only restore
  inside a pool-copied image leaves the page as it is, reports success and
  lets the sync run ([vmem-denied] madeira-bcd: restore ... refused).
* Build 241 on the device (logs 11:20, 11:21): the repatch works (16
  [mach_exc] UNALIGNED-REPATCHED per run); one run got through the intro
  videos (choppy) and stopped as the main menu appeared. Next fault, both
  runs: `ldaddal w7, w8, [x6]` on 0x...b6267e (guest 0x1408df521, x86 lock
  add/xadd on a misaligned dword), which only the LL/SC and CAS forms were
  emulated for. Build 243: LSE atomics (LDADD/LDCLR/LDEOR/LDSET/LD{S,U}{MAX,MIN}
  and SWP, any A/L) on a misaligned operand are emulated on the exception
  server like CAS ([mach_exc] UNALIGNED-LSE). The owner's madeira.cfg still has
  inproc-sync = 0 from the hang hunt (madsync off), a likely part of the
  choppiness.
* Build 243 (log 11:55, madsync back on): no unhandled fault at all; 11
  [mach_exc] UNALIGNED-LSE (ldaddal) and 16 UNALIGNED-REPATCHED handled. The
  game ran 55 s and was killed by jetsam: footprint 8178 of 8192 MB
  (internal ~3.0 GB, compressed ~3.3 GB, external ~0.55 GB, swap tier 2.1 GB
  file-backed). The pre-switch runs sat at the same edge (peaks 7687 and
  7984 MB) and survived. Next: memory pool (mempool-mb, upstream's
  MadeiraMemoryHost) and/or swap coverage "wide", one at a time.
* 32-bit Crysis on build 243 (log 11:57): the IAT fix works (wow64.dll,
  libwow64fex, ucrtbase, kernel32, kernelbase all bind; 20+ `[vmem-denied]
  madeira-bcd: restore ... refused` lines), wow64 initialises and the game's
  own code runs (creates C:\users\...\My Games\Crysis, LogBackups). Then
  CPUID 0x80000002: FEX's Function_8000_0002h indexes PerCPUData with the raw
  host CPU number (1 entry on iOS, CPU 3+) and strlen()s a garbage pointer
  (0xfff68000; pc ntdll strlen, lr xtajit.dll Function_8000_0002h+0x30).
  RunFunctionName wraps the index, the leaf entry points did not. Build 244:
  tools/patch-fex-ios-cpuid-index.py for both modules; the WOW64 module
  (xtajit.dll, until now built by hand with build/fex-wow64/build.sh) is now
  built in CI by tools/build-xtajit-wow64.sh (cached FEX/build-wow64; the
  committed module stays if the build fails or its exports differ).
* 32-bit Crysis on build 244 (log 12:25): past CPUID; loads CryGame,
  CrySystem, CryAction, d3dx9/d3dcompiler_43, CryInput, CrySoundSystem
  (fmod), CryFont, CryAISystem, CryAnimation, Cry3DEngine, CryScriptSystem,
  CryEntitySystem; 489 presents in the first 30 s; ran ~4 minutes compiling
  shaders (d3dcompiler reflection fixmes). Then libwow64fex+0x11f644: the
  TlsGetValue shim with x18 = 0 read TlsSlots[20] at 0x1520 -- the same
  GetCurrentTEB() problem as GoW's on ARM64EC. Build 245 applies
  tools/patch-fex-ios-teb-tsd.py to the WOW64 module too (its IosTebTsdOffset
  is published into the same extern "C" variable).
  (That build ran as run 246, e449b17; main fast-forwarded to it.)
* Crysis intro videos, 30 s pause between each (same log, owner: "every gap
  about a minute, the videos themselves smooth"): the gaps are exactly 30.0 s
  of near-idle CPU (12:25:49.7 -> 12:26:19.7, 12:26:38.6 -> 12:27:08.5, ...).
  The video thread (00b8, then 00dc) calls SuspendThread on ITSELF every frame
  and is resumed by the main thread. On iOS a self-suspend never stops the
  thread (SIGUSR1 never reaches usr1_handler, task #32), so it spun ~46k
  SuspendThread/s and the server count sat at MAXIMUM_SUSPEND_COUNT
  ([srv-suspend] "count 127->127"). When the video ended the thread reached
  NtTerminateThread(self), whose zero-timeout server_select waits while the
  thread is suspended -- forever (teb 0x7103090000 parked in
  wait_select_reply for the rest of the log; no "read_request EOF" for 00b8
  or 00dc), so the main thread sat out a 30 s join timeout. Build 247:
  NtSuspendThread (build/ntdll-unix/thread_ios.c) waits like wait_suspend()
  when the target is the calling thread ([self-suspend] log line).
* Build 247 on device (log 2026-09-30 13:19 + screen recording): the intro
  gaps are gone ([self-suspend] #1.. for tid 00b8) and Crysis reaches the
  first level (beach, nanosuit boot HUD) at ~55 FPS, GPU ~5-6 ms, via
  CryRenderD3D10 -> DXMT d3d11 (feature level 10_0). Rendering bug: parts of
  the scene (nearby foliage, it looks like) are replaced by long vertical --
  and some horizontal -- streaks spanning the screen, i.e. vertices thrown far
  out (clip w near 0 or garbage) rather than a texture problem; rocks, beach,
  trees at distance, weapon and HUD are fine. No DXMT warnings in the log.
  There is no D3D11 capture tool yet (CAP sheets are madeira_d3d12 only).
  Asked the owner to bisect with the in-game Advanced settings (all Low, then
  raise Objects / Shaders / Game Effects one at a time) and to try the `-dx9`
  launch argument (DXMT d3d9 path) for comparison.
* Second recording (13:55): settings had been at Low; raised a notch, far
  vegetation renders correctly and the broken shapes change: streaks radiate
  from vanishing points (vertical toward zenith/nadir, horizontal toward the
  horizon), so vertices of some nearby meshes are displaced very far in WORLD
  space, not a screen-space pass. Reviewed and ruled out as obvious causes:
  airconv vertex-format pulling (half/snorm/BGRA paths look right), wine's
  d3dcompiler reflection (skips are STAT/signature padding; D3D10 GetDesc
  maps to D3D10_SHADER_DESC). Open candidates, none proven: (1) constant
  buffers bound smaller than the shader declares -- airconv loads cb[] with no
  bounds and Metal has no robustness, so D3D's zero-fill becomes garbage
  (a fix needs the declared size at encode time; MTL_SM50_SHADER_ARGUMENT is
  also mirrored in research/madeira-d3d12/src/madeira_ir_abi.h, so do not
  grow it without updating both); (2) 16-bit index buffer offsets that are
  2 mod 4 (odd StartIndexLocation) passed straight to Metal. The -dx9
  comparison is still pending.
* -dx9 renders Crysis correctly (owner, 2026-09-30) but at ~28 FPS instead of
  ~55-60 (the S25 Ultra runs it at ~110 FPS with DXVK 2.7.1), so the D3D10
  path is the one to fix. Build 248: tools/patch-dxmt-cb-short.py parses each
  shader's dcl_constantbuffer sizes (SHDR/SHEX, no airconv ABI change); a
  bound buffer shorter than declared gets a zero-padded copy in the encoder's
  argument buffer, refreshed every draw ([cb-short] lines), and 16-bit index
  offsets that are not a multiple of 4 are counted ([idx-align], log only).
  It only reaches 32-bit games: the i386 farm is rebuilt from research/dxmt,
  the 64-bit PE d3d11.dll is still the committed binary. If [cb-short] never
  appears, candidate (1) is refuted.
* Performance (the -dx9 log 14:53 and the D3D10 log 13:19 alike): the main
  thread 0024 ran 0 ms on P-cores and ~600 ms/s on E-cores (2.1-2.6 GHz),
  [cpu-split] 88-97 % x64 JIT, while the game's time-critical thread (0060)
  ran on P-cores at 4.2 GHz. wineserver's apply_thread_priority (__APPLE__
  branch of wine/server/thread.c) sets Mach precedence/throughput/latency
  policies from the Windows priority at thread start; for NORMAL threads that
  appears to override the USER_INTERACTIVE QoS the guest threads ask for.
  Build 249: tools/patch-wine-thread-qos.py skips those policies below the
  realtime band on WINE_IOS ([thread-prio] lines;
  MADEIRA_WIN_THREAD_PRIORITY=1 restores them). Check [xp-t] for 0024's P ms.
  The owner also has the in-game 60 FPS cap on; to be turned off for the test.
* Build 249 on device (log 15:46, 60 FPS cap off): ~92 FPS, GPU ~4 ms; the
  streaks remain, and the owner saw that they only appear where trees or
  branches are in view (rocks, sea, sky fine). [cb-short] fired (cb0 80/74,
  cb1 9/4..42, cb2 4/3 vec4 and more), so short constant buffers were real but
  not the cause; [idx-align] counted 659456 16-bit draws with offset 2 mod 4.
  [thread-prio] showed Crysis's main thread toggling base 0/15 and the policies
  skipped, yet 0024 still ran 0 ms on P-cores. Root cause of that: the guest
  main thread is created in WineProcessBridge.m with
  pthread_attr_setschedparam(priority 20), a fixed priority, so Darwin refuses
  pthread_set_qos_class_self_np (EPERM) -- USER_INTERACTIVE and the ECO switch
  never applied to it. Build 250: the thread gets its QoS through
  pthread_attr_set_qos_class_np instead ([main-qos] line), and
  tools/patch-dxmt-idx-align.py copies misaligned 16-bit index ranges to a
  4-byte aligned place in the argument buffer (MADEIRA_IDX_REALIGN=0 = off).
  The ECO toggle is in the session menu (Battery saver (ECO)) and the ECO pill
  of the Madeira performance overlay, not in Apple's Metal HUD.
* Upstream merge 2026-09-30 (100 commits up to fdbdef7, "round 3"): Steam
  owned library (sign-in, downloads, installs), fastsync as the DEFAULT sync
  engine (madsync only with inproc-sync = 1; Settings > Sync engine), NSI
  network tables and dnsapi unixlib, Dock GDI table for 32-bit programs, touch
  control glass faces, rebuilt 64-bit/aarch64 DLLs; pins FEX 26859e1 (#5:
  CPUID table bound -- tools/patch-fex-ios-cpuid-index.py now detects it and
  does nothing), wine 4f5b197, madeira-dock 3cadfbe. Kept ours: game cfg
  env block before the fastsync default (a game's env.MADEIRA_FASTSYNC wins),
  pointerMax, the JIT-pool second-session guard, the controls opacity, the
  memory-pool picker and MemoryHostTest row. The session menu's ECO toggle
  moved from Display to its own CPU section (the owner looked for it there).
* Build 251 on device (log 16:37): [main-qos] rc=0 class 0x21 -- the guest
  main thread now runs on P-cores (0024 ~300 ms P per 300 ms), so that fix
  works. The tree streaks are unchanged, but neither DXMT fix had actually
  run for most draws: both skipped GpuManaged allocations, and Crysis's
  static buffers are GpuManaged (578 of 653 buffers, [mem-census]). On iOS a
  GpuManaged buffer is CpuPlaced and Managed does not exist, so the CPU
  mapping IS the storage; the next build copies from it too and logs
  "encode: realigned / zero-padded copy bound / skipped" counts. The session
  menu the owner uses in a game is LibraryHUD's (Library.swift), not
  SessionUI's: the ECO toggle now also sits there under a CPU heading.
* Build 254 (7fe376d, first build of the round-3 merge) FAILED at "Verify all
  linked archives exist": libntdll_unix.a was not built because upstream's new
  nsi_ndis_ios.c / nsi_ip_ios.c did not compile -- RTM_IFINFO, RTA_IFP and
  RTF_LLINFO undeclared. Our CI configures Wine against the iPhoneOS SDK
  (no <net/route.h>), so HAVE_NET_ROUTE_H is undefined and ndis.c/ip.c never
  include upstream's shims/net/route.h (upstream builds with a macOS-configured
  config.h). Fix: both wrappers define HAVE_NET_ROUTE_H when config.h does
  not. (How the error was found: the job log is only 2649 lines; get_job_logs
  with tail_lines=2649 saves it to a file that can be grepped.)

### Build 226: first green IPA after the switch (2026-09-29, run 36595079405)
Commit 17088ab (main fast-forwarded; the automatic main run 227 cancelled).
Native ABI e708a9072e35d90d, shader cache identity 1f62cb76a67abb1f: packs
5-7 do not install over it. Contains everything under builds 222-223. The
i386 farm came from the CI cache. Not in it: the AVX variant of
xtajit64.dll (the committed module does not match a rebuild of FEX
2838f3b, so tools/build-xtajit64.sh refuses to ship one); the per-game
"AVX / AVX2" switch has no effect until that is sorted out. Device test
pending: library + madeira-bcd sections, God of War with its config.

### Build 223: library first, madeira-bcd home as a choice (2026-09-29)
Owner's request: upstream's interface by default, ours as a separate option,
our per-game options inside upstream's game page, every upstream feature.
* Also merges upstream a15332c (MadeiraMemoryHost app extension: memory
  owned by another task, used by the swap tier first; `mempool-mb = N` in
  madeira.cfg or Settings > Memory & sync, off by default; needs `swap-mb`)
  and d5a8e0a (library tab bar). The extension's bundle id was changed to
  `com.willfaust.mythicemu.MemoryHost` (must be prefixed by the app's id).
  Worth trying for God of War's memory: `mempool-mb` next to `swap-mb`.
* Interface: `FrontendChoice` has a third stored value "bcd". RootView
  starts in ContentView (library / developer) unless it is "bcd". Picker:
  library Settings > Interface, madeira-bcd home settings; the developer
  interface has a "madeira-bcd Home" button.
* `LibraryBCD.swift`: the madeira-bcd sections of `LibraryDetail` (AVX,
  Wine VCRT, NVIDIA; MetalFX, frame gen, D3D12 switches, game config file;
  Home Screen link), keyed by the Windows path as in HomeView, so both
  interfaces share settings. Library launches call `BCDLaunch.applyLibrary`
  (update pack env, the options, per-game session log). Resolution picker:
  "Screen shape for MetalFX 1.5x"; FPS picker: 40 FPS. Long press: Play /
  Game settings. Settings > Interface > "Add every game in drive_c".
  Shortcuts (madeira://play) start the library entry in library mode.
* Builds 222-224 failed on leftovers of 125hz's series: a brace lost in
  the virtual_ios.c re-apply, an SDK field in server_ios.c, 125hz's DXMT/nsi
  PE DLLs, Swift calls into 125hz's removed cursor helpers, and 125hz's
  fastsync wineserver/bridge sources (9 undefined symbols at link). Every
  file only 125hz had changed since the base now equals upstream (or is gone).
  Still 125hz's on purpose, because they build and link against upstream:
  app-side JIT pool handling (JITAllocator, StikJITHelper, the ml1330 early
  pool in ContentView) and sysparams_ios.c's weak diagnostics hooks.
* RDR2: upstream has no separate RDR2 package; its RDR2 bring-up lives in
  the runtime we merged (ntdll-unix, madeira_d3d12, the converter service,
  swap tier), plus `research/HANDOFF-rdr2-arm64ec-hooks.md`.

### Build 222: switched to upstream (2026-09-29, owner's decision)
Merge commit `4ccfcb5` brings in upstream main `15157e3` (77 commits: Library
front end, Steam sign-in, Madeira Dock, GuestDisplay/HardwareInput, WoW64,
DXMT's D3D9, swap-tier coverage modes + census, the DXIL conversion cache and
one-pass conversion). How the overlaps were resolved:
* `build/ntdll-unix/virtual_ios.c`: upstream's file, then our commits since
  `735e323` re-applied in order. Skipped as superseded: 6442b98/3115f50
  (our early storage-backed memory) and 81a799a (our swap floor). Our
  partial-page `decommit_pages` stays, now with upstream's
  `ios_swap_release_range` before the mmap-over.
* `swap-min-kb` now exports `MADEIRA_SWAP_COVERAGE=blocks` plus
  `MADEIRA_SWAP_MIN_KB` (upstream reads the floor only in blocks mode); an
  `env.MADEIRA_SWAP_COVERAGE` line still wins. Upstream prints
  `[swap] coverage=...` and a census line every 30 s instead of our
  `[swap] ml1077 stats`.
* `madeira_d3d12.c`: our PE shader cache (`mad_ir_convert_cached`) wraps both
  calls of upstream's one-pass conversion (first try and too-small retry).
  `cs-dump = 1` or `MADEIRA_D3D12_CS_DUMP=1` turns the compute dump on.
* `madeira_ir_unix.mm`: upstream's `mad_sc_path_ext` (DXIL cache files share
  `shadercache/`) keeps our `.mdsc` pruning; the hull/domain entry-name
  fallback applies to upstream's reflected name.
* `tools/patch-dxmt-framegen.py`: new present-hook anchor (DXMT now guards
  `ios_frame_encode_present` with `madeira_frame_hooks_on()`). The other DXMT
  patches apply unchanged to `a5e0cd3`. Upstream now has its own 30 FPS
  mode 3; our frame-limits patch's mode-3 branch is dead code, mode 4 (40)
  still works.
* CI: builds FFmpeg (`build/ffmpeg`, cached; the app links libav*.a) and the
  Dock host (`build/madeira-dock`, may fail without breaking the build).
  The 32-bit `i386-windows` farm is no longer committed (upstream's rule);
  CI builds it with `build/wine-i386/build.sh` (cached per wine/DXMT
  revision, continue-on-error: without it only 32-bit programs fail).
  125hz's committed DXMT/nsi PE DLLs in aarch64-windows/arm64ec-windows were
  replaced by upstream's (they called 125hz's DXMT unix slots).
* Launch log prints the game's config file (`[game-cfg]` lines).
* Removed 16 host tests from 125hz's WoW64 series that probe code no longer
  in the tree; `ConfigCatalog.generated.swift` regenerated (it lists our keys).

### Build 220 device results (God of War, logs 2026-09-29 14:42 / 14:54)
* Frame generation works: `[framegen]` generated a frame for every real one,
  HUD 40 FPS shown / 20 rendered, "Frame Interpolator Enabled". Costly: GPU
  8-10 -> 23-33 ms per frame, and the game waits ~29 ms per frame for a
  drawable (two presents per game frame on a 3-drawable pool), so the real
  rate fell from ~30 to ~20.
* The MetalFX output was 2084x960 (2x), not 1563x720, although DXMT logged
  `d3d11.metalSpatialUpscaleFactor=1.5`. The source reads it as a float, but
  the committed d3d11.dll may predate that, so 1.5 is not honoured. As a
  result the interpolator ran at 2 MP. Fix candidates: a factor-2 "fill"
  size (782x360 -> 1564x720), or MetalFX + interpolation in winemetal
  itself (the descriptor's `scaler` property lets the interpolator work at
  the scaler's input size).
* In-game: FSR 2 Ultra Performance was on (render 428x240 for a 1042x480
  output); Performance costs RAM; FSR off runs out of memory. With FG,
  ~280-300 MB stayed free. The VMCENSUS/totalphys run has not been sent yet.
* 14:54:09: the log stops at "Starting God of War" (22 lines): the app died at
  launch, cause unknown.

### Build 220: frame generation, "Fill with MetalFX 1.5x" (2026-09-29)
* God of War with build 219 + the four config lines: 10+ minutes of play
  (log 13:48). Swap tier 2.1 GB file-backed; `turned away`: under 1 MB
  0.7 GB, outside the guest band 11.9 GB (cumulative; mostly FEX's per-thread
  arenas at 0x7c.., which must stay anonymous: CpuStateFrame at +0x1140, see
  ml181), partly committed 0.1 GB. Textures 572 MB, Metal total 1.46 GB,
  footprint ~7.6 GB with 3.3-3.7 GB compressed. ~28-44 FPS, game CPU
  22-28 ms/frame, GPU 8-10 ms: GPU has room; memory limits resolution.
  Next memory step: one run with `env.MADEIRA_VMCENSUS = 1` for the
  per-band breakdown; `totalphys = 6144` to see if the game sizes its
  caches down.
* Frame generation (docs/madeira-bcd.md, App): first device test pending.
  Unknowns: motion vector scale/sign semantics, whether BGRA8 is accepted,
  pacing with the drawable pool. `[framegen]` lines say which.
* SDK probe workflow (.github/workflows/sdk-probe.yml): CI has Xcode 26.3 /
  iOS SDK 26.2; MTLFXFrameInterpolator.h was read from there.

### Build 219: swap floor knob (2026-09-29, run 36554968715, native ABI d22451074a1a1504)
* `swap-min-kb` (madeira.cfg or a game's config) lowers the swap tier's 8 MB
  eligibility floor; `[swap] ml1077 stats` prints every third heartbeat with
  the MB turned away by reason. Packs 5/6 are native-ABI 48a89bc6... and are
  ignored by 219; 219 already contains their changes.
* God of War config to try: `dxmt = d3d11.mipClampBC=2`,
  `env.WINEDEBUG = err+all,err-virtual,fixme-all`, `swap-min-kb = 1024`,
  `swap-mb = 6144`.

### Other games tried 2026-09-29 (IPA 218 + pack 5)
* God of War (2018, D3D11): the owner started
  `C:\God of War\_Windows 7 Fix\dxvk-1.10.1\GoW.exe`, a copy inside a
  DXVK "Windows 7 fix" folder. Its DLLs (libScePad, libSceJobManager,
  bink2w64, libSceGnm, libSceGpuAddress) are not next to it, so the loader
  stops with 0xC0000135 before any frame. Start the game's own GoW.exe in
  the install root instead. DXVK itself is Vulkan and cannot run here: DXMT
  is the D3D11 path, so do not use the DXVK DLLs.
* God of War, second run with the right exe (log 13:02, 43 MB): it reaches
  the main menu (~16-27 FPS); on New Game the footprint climbs to 7.7 GB and
  jetsam kills it. `[mem-census] tex-private live=4051MB` (12,411 textures),
  buffers 785 MB. The automatic BC mip clamp (dxmt ml2000, threshold 1536 MB
  headroom) engaged only at footprint 7188 MB and clamped 6 textures:
  too late for a title that loads 4 GB of textures at once. Workaround with no
  build, in the game's config: `dxmt = d3d11.mipClampBC=1` (drops the top mip
  of every eligible BC texture, ~4x less memory for them). 95 % of the log is
  `fixme:d3dcompiler:skip_u32_unknown` from D3DReflect on 4 threads:
  `env.WINEDEBUG = err+all,err-virtual,fixme-all` in the game's config.
  Candidate follow-up (dxmt, IPA): a larger auto threshold or a footprint
  trend trigger.
* Third run (13:11) with both lines: gameplay reached (a few axe swings),
  textures 4051 -> 1050 MB, Metal total ~1.7 GB, log 5 MB. The footprint
  still climbs to ~8.0 GB and sits at the limit for 2+ minutes (compressed
  3.2 GB) before jetsam. Not a leak: the game's own RAM is the rest. The swap
  tier (swap-mb 3072) already backs its big blocks (~1.6 GB), but
  `ios_swap_eligible` refuses commits under 8 MB, outside [0x70,0x7c), or not
  entirely fresh. Next without a build: mipClampBC=2 plus lower in-game
  settings. With a build: a madeira.cfg knob for the swap floor (e.g. 1 MB)
  and a breakdown of the footprint by region kind.
* Far Cry 5 (D3D11): it gets past the loading screen to a black window
  (d3d11/dxgi/winemetal loaded, no device created yet). ~50 first-chance
  write faults on read-only pages are handled (protection layer). Right after
  `EasyAntiCheat_x64.dll` (a 52 KB module from the game folder) loads and its
  TLS callbacks run, FC_m64.dll+0xe0a5d68 calls through a NULL pointer
  (AV EXEC of 0) and the game exits with 0xC0000005. Anti-cheat modules do
  not work in this environment; not investigated further.

### Pack 6: F0 no longer poisons the session (logs and videos 2026-09-28 20:35-20:41, pack 5)
* Videos matched to the 20:35 log through the HUD frame number (roughly the
  present count). At 20:36:41 (F1, no switch yet) the scene is intact but
  edges are jagged, dotted and blocky: character outline, fur, rock and
  wooden structures. It looks like the game's temporal upscaler/AA not
  resolving; libxess.dll is loaded, so the owner is to try the in-game
  upscaler options. 20:37:19 is F0: garbage expected. 20:37:44 is F1 AFTER
  F0: the scene goes black and blotchy.
* Cause of the last one: every GPU fault under F0 (no fences, i.e. races by
  design) was treated as a broken shader. `mad_fault_report` marked the
  cs_main pipelines to skip (15+ in that run) and switched the fault
  diagnostics on (one pipeline per compute encoder, labels) for the rest of
  the session. All F1/F5/F6 observations after an F0 test in the same run
  were invalid, and so was the 18:56 log. Pack 6: faults are not marked
  while F0 is in effect or for 8 presents after it; leaving F0 clears the
  skip list and the diagnostics.
* 20:41 (MetalFX 2x): the C++ exception fast-fail again, this time in
  gameplay, with the same stack (GhostOfTsushima+0x449681 recursion,
  +0x40a99d, VCRUNTIME140_1 frame handler, handler +0xd15f0c). Pack 5 did
  not fix it, so it is not the device list race. Next step is native
  (unwind / dispatcher-context diagnostics), so an IPA.
* 20:39 async-submit = 1: ExecuteCommandLists costs the game thread 0.03 ms;
  the worker is busy ~16 ms per frame and the game waits on its fences
  10 ms per frame (24 %) at the end. Thermal was WARM from the start; no
  clear win yet.

### Pack 5: device list race fixed (logs 2026-09-28 18:53 and 18:56, IPA 218 + pack 4)
* 18:56 crash: AV in the ntdll heap (ntdll+0x29634) under
  `device_CreateSampler -> mad_note_sampler -> mad_grow` (realloc) on thread
  00f0 while five game threads were streaming a new area. Symbols came from a
  local `-g` build of 6bbd6b8: same .text size as pack 4, so the RVAs match.
  `d->samplers`, `srv_res` and `uav_res` were grown, appended and
  swap-removed without a lock, although D3D12 device methods are
  free-threaded; two reallocs of one array corrupt the heap, and the heap
  lock left held gave the 60 s `RtlpWaitForCriticalSection` timeout that
  follows. It happened right after an F0 -> F1 pill switch, but the switch is
  not involved. Pack 5: `list_lock` (SRWLOCK) guards the three lists;
  membership is O(1) through `srv_slot` / `uav_slot` (the old linear scan
  covered ~15,000 textures per view creation); the per-draw fallback loops
  and `mad_texture_of_view` read under the shared lock. The heap corruption
  may also explain some of the intermittent crashes before this one.
* 18:53 crash: the known C++ exception fast-fail (handler
  GhostOfTsushima.exe+0xd15f0c, 0xC0000409) while loading into the world;
  see "Build 191 results". Still open. A corrupted heap is one possible
  source, so check whether it recurs with pack 5.
* Frame time (18:56, 1280x720, F1): steady 22-27 ms per frame. ExecuteCommandLists
  takes 4-6 ms of that: Metal encode calls 0.66 ms (583 calls),
  encoder open+end 1.76 ms (134 encoders), and the rest is the replay itself. Present
  0.25 ms, the game blocked on fences 0 ms. The remaining ~18 ms is the
  game's own CPU time under emulation, so draw batching on our side can win
  1-2 ms at most. ECL spikes of 50-550 ms per frame are first-draw pipeline
  compiles (`pso-lazy`) in new areas; the shader cache removes them on the
  next visit. useResource dedup skips ~55 % of the entries in gameplay.
* `[frame] ml1050` always says "no Present reached the presenter" for D3D12:
  that reporter only sees DXMT's presenter. Not a bug in the game path.

### Build 218: saves backup, Home Screen shortcuts, useResource dedup (2026-09-28)
* `madeira_d3d12`: one useResource per resource and encoder (`mad_use_seen`,
  `use-dedup`, default 1); a draw's entries are committed only after its
  chain was encoded. The encode split line reports the skipped entries.
* Settings > Saves (backup/restore zip) and `madeira://play?exe=...`
  shortcuts (see docs/madeira-bcd.md, App).
* 217 was CI verification only; the owner installs 218 (nothing had been
  installed since 214).

### Build 217: GoT specks/smears flags, experiments in the sheet, storage (2026-09-28)
Log analysis (13:21 and 14:04 logs, builds 211/212):
* 13:21 "40-45 then 20 FPS": the `[perf] ml1108` GPU time per frame jumps
  from 17-20 ms to 37-44 ms while ExecuteCommandLists stays ~2 ms; the game
  then waits 33-39 ms/frame on its fences. GPU-bound, the particle
  tessellation growth capped in 213 (`dxil-tess-max-factor`).
* 14:04 gameplay: frame 38-42 ms = GPU 19-20 ms (not the limit) +
  ExecuteCommandLists 10-16 ms ON THE GAME'S RENDER THREAD (~630 draws,
  ~5,600 commands a frame) + 4-8 ms fence waits. `async-submit = 1` moves our
  encode to a worker (RDR2 upstream saw no gain because its render thread
  was not the critical path; GoT may differ). Now a picker in the game sheet.
* ~220 GPU encoders a frame, each waiting for the previous one under
  fence-chain 1; the F6 picker/pill lets passes overlap.
* Render passes always Load/Store (no pending clear); census frames show
  ~225 MB loaded + ~241 MB stored, 170 MB of it never used again in the same
  list. Cross-list use is unknown, so no DontCare yet -- a candidate for a
  frame-level analysis.
Also in 217: the `[perf] encode split per frame` line (time inside the Metal
encode unix calls vs encoder open/end vs the replay itself, and the
useResource entries per frame) to find where ExecuteCommandLists' 10-16 ms
go before optimising it; Settings > Storage; the D3D12 experiment pickers.
(Run 216 was the automatic main-push duplicate, cancelled.)
The specks in the owner's screenshots sit on the fire-lit smoke and rock by
the bridge and come and go between frames: NaN/Inf, most likely through the
NaN-cleared velocity target into the temporal resolve, or particles killed
with an infinite position. Build 217 turns on `IRCompatibilityFlagSampleNanToZero`
and `IRCompatibilityFlagVertexPositionInfToNan` (`msc-sample-nan-zero`,
`msc-position-inf-nan`, both default 1; the shader cache keys on them, so the
first start converts again). (The comment in
`madeira_ir_unix.mm` was corrected in 218:) SampleNanToZero flushes NaN sampling
COORDINATES to zero (man page), it does not rewrite sampled values -- the
velocity NaN markers the game tests stay intact.

### Build 215: update packs, per-game config, MetalFX, thermal (2026-09-28)
The owner is tired of signing and installing an IPA per experiment, so the
iteration loop moved in-app (see section 2, "Update packs"). Also:
* `metalfx-upscale = <factor>` (per game from the sheet: Off / 1.5x / 2x):
  the D3D12 swapchain runs Apple's MetalFX spatial scaler on a 2D view of the
  back buffer into a private texture of factor x size, and the present blit
  copies that into a drawable of the same size (`mad_swap_make_fx`,
  `mad_present_run`). D3D11 games get DXMT's own MetalFX swapchain
  (`DXMT_METALFX_SPATIAL_SWAPCHAIN=1`, `d3d11.metalSpatialUpscaleFactor`).
  Meant with a small screen size (960x540, 1280x720) for frame rate.
* Per-game starting FPS limit (`fps-limit` = 30/40/60/max/raw) and the
  tessellation cap (`dxil-tess-max-factor`) as pickers.
* The FPS overlay shows the thermal state (OK/WARM/HOT/CRIT); `[thermal]`
  lines mark transitions and every `[present]` line carries it. Use it on the
  "starts 40-45, sinks to 20" report: a HOT at the drop means clocks, not us.
* Note: the D3D12 runtime presents through winemetal's
  `MTLCommandBuffer_presentDrawable`, so the Session panel's 30/40/60 caps
  already apply to Ghost of Tsushima.

### Build 214: upstream sync (2026-09-28)
Merged willfaust/madeira 9e9dfb6, e39be62, 735e323. Upstream vendors the
Metal Shader Converter 4.0 beta 2 public headers under
research/madeira-d3d12/third_party/metal-shader-converter and deps.sh now
hash-checks them and the tracked iOS library. Our CI does not go through
deps.sh: build/dxmt-ios/build.sh (kept ours) takes MADEIRA_MSC_INCLUDE, the
4.0.1 headers staged from the msc-private draft release, and keeps the stub
fallback instead of upstream's hard stop. Upstream moved the wine pin to
willfaust/wine d2808652; 125hz pr/wow64-core does not contain it, so the
pin stays at c9c186e. Build 214 green.

### Build 213: particle tessellation cap; the loading-screen freeze
* `[probe]` (log 2026-09-28 14:04) settles the FPS drop: the particle draws
  (`ls_SetColor`, `vs_SetColor`, `vs_SetColorCombinedAlpha`, 4 vertices x N
  instances) go 16 -> 2,929 -> 5,052 -> 6,897 -> 7,692 instances within
  seconds and then vary with the fires: not a leak, the game's particles.
  Each is a tessellated quad (max factor 9, up to 162 triangles) drawn three
  times through the emulation, and in the 13:21 log the GPU time climbed
  17 -> 44 ms as they spawned. Other indirect pipelines are steady. Build 213
  clamps the hull's max factor to 3 for pipelines declaring <= 16 (the water
  declares 64 and keeps it): madeira.cfg `dxil-tess-max-factor`, 0 = off.
* Loading-screen freeze (log 14:03): `RtlpWaitForCriticalSection ... blocked
  by 00bc`; 00bc was calling GetThreadContext on another thread thousands of
  times and getting `rip=0 rsp=0 flags=00100002` (no CONTEXT_CONTROL: the
  server had no native capture). The unix NtGetContextThread now fills the
  control (and integer) registers from the target's saved x64 state
  (ChpeV2CpuAreaInfo->ContextAmd64) when the server returns none; log
  `[ctx] madeira-bcd get ... returning the target's saved x64 state`.

### Build 212: probes for the GPU time that grows (log 2026-09-28 13:21)
* Build 211 draws the indirect tessellation (`DXIL tessellation: 3117 drawn
  (3117 indirect)`; every tessellation draw in gameplay is indirect). The
  smears and dark specks over the bridge did not change, so they are not the
  particles that were skipped.
* The owner: 40-45 FPS at first, ~20 within seconds. The perf lines agree:
  GPU per frame 17-18 ms -> 37 -> 42-44 ms (one window 61 ms) while the lists
  stay the same (~60 draws a list, 600-list totals flat) -- the GPU's own work
  grows. Best guess: a GPU-side count that is never reset (an append counter,
  so ever more particles/instances are simulated and drawn), which would also
  explain accumulating specks.
* Build 212 adds `[probe]` lines: every 3 s per pipeline the first argument
  record of each indirect draw/dispatch is copied (helper kernel
  `mad_probe_words`) to the CPU-visible ring and the previous copy is logged.
  A pipeline whose counts climb is the lead. madeira.cfg `ind-probe = 0`
  turns it off; at most 1,500 lines.

### Build 211: indirect DXIL tessellation draws (the particles)
The owner's screenshots (build 209) still show yellow brush-stroke smears and
clusters of dark specks over the bridge, where the fires' smoke and embers
are. The tessellation pipelines in use are the water and `ls_SetColor` /
`ps_SetColor_MultiLight`: 4-control-point patches, max factor 9 -- lit
particle quads -- and ~2,700 of their draws a run came through ExecuteIndirect
(GPU-driven particles) and were skipped. Build 211 draws them:
* `research/madeira-d3d12/src/pe/mad_kernels.metal` (kernel
  `mad_tess_indirect_args`) is compiled to a metallib by
  `tools/build-madeira-d3d12-dll.sh` (`xcrun -sdk iphoneos metal`) and embedded
  (`-DMAD_HAVE_KERNELS`, `mad_kernels_metallib.h`). Without xcrun the DLL
  builds without it and those draws stay skipped (log: `helper kernels: not
  built in`).
* Before such an ExecuteIndirect the render pass is split and one compute
  pass turns each argument record into MTLDispatchThreadgroupsIndirectArguments
  (ceil(count / (patches per object threadgroup x control points)) x instance
  count) in a 4 MB shared ring; each record is then drawn with
  `drawMeshThreadgroupsWithIndirectBuffer`, the D3D record bound at index 4
  for the object stage as for direct draws. tools/patch-dxmt-dxil-tess.py sets
  the object threadgroup memory for the indirect mesh draw too.
* Log: `helper kernels: ready ...`, `indirect tessellation: N record(s) ...`,
  and `DXIL tessellation: N drawn (M indirect)` in the ml1050 line.

### Build 210: the 209 test (log 2026-09-28 10:13, video)
* The C++ fix is applied (`[pc2fh] ... now maps`); the owner saved five
  times without a crash. The RGBA32 clear is exact now (`UAV clear value
  0xbf800000 0x4cbebc20 0 0: exact pattern buffer`), the big smears are gone
  and the GPU time dropped from 52-56 ms to 18-19 ms a frame at 1564x720
  (15 -> 20-22 FPS): the uncleared buffer was also costing GPU time.
* Left: dark specks and blocky haze near the bridge. Two leads:
  - 4 `ClearUnorderedAccessViewUint on a texture view the runtime does not
    know; skipped`. Now the named resource is cleared (the recorded view's
    sub-range, or all of a single-mip texture in its own format), and the log
    says why the view was unknown.
  - `indirect draw on a geometry-shader pipeline is not implemented` is the
    only skip site: 2,696 draws a run (`skips by site: L4436`). The only such
    pipelines are the DXIL tessellation ones (water, `ls_SetColor`). The log
    line now names each pipeline; implementing indirect tessellation draws
    (the object threadgroup count comes from the GPU-side arguments) is next
    if they matter.

### Build 209: the 208 test (log 2026-09-28 09:31, video, 1564x720 "Fill")
* **Smears with a still camera** (video, first 10 s: directional streaks and
  blocky patches behind the cart, the "dark patches in the air"). The log had
  `ClearUnorderedAccessViewUint on texture 'Texture' (view format 2 ...
  values 0xbf800000 0x4cbebc20 0 0) is not supported; skipped`: an RGBA32
  clear to (-1, 1e8, 0, 0), typical of a min/max depth or velocity tile
  buffer, left uncleared. Texture UAV clears only took texels that repeat
  every 4 bytes; the pattern buffers now repeat a 16-byte period, so 8- and
  16-byte texels are cleared exactly (log: `UAV clear value ... exact pattern
  buffer`). If the smears stay, the next suspects are the 4 clears on "a
  texture view the runtime does not know" and the 4 skipped indirect draws on a
  geometry-shader pipeline.
* **C++ fix still not applied**: `[pc2fh] no zero padding in the last .text
  page (000880c0..0008c000)`. On the device the tail of ntdll's last .text
  page holds file bytes (raw size 0x80000 > VirtualSize 0x780a5), not zeros.
  That range is outside every section, so the trampoline now goes at its
  start regardless of content; the pool copy is only refused when its bytes
  differ from the image's (another patch). Host test with a garbage tail:
  patched at RVA 0x880c0, idempotent, refused with foreign pool bytes.
* Water: DXIL tessellation now draws (`DXIL tessellation: ~1900 drawn`, no
  REFUSED). GPU time at 1564x720 is 52-56 ms a frame (overlay), so at that
  size the GPU is the limit (~15 FPS).

### Build 204: the three failures of the 203 test
* **C++ exception fix not applied.** `[pc2fh]` refused with "padding in use":
  the trampoline went at the end of the section gap, which this binary uses.
  It now goes in the first 48 zero bytes after `.text`'s end inside the last
  executable 16 KB page (verified offline against the real
  vcruntime140_1.dll: RVA 0x880d0). Log: `[pc2fh] ... now maps`.
* **Water: VS conversion.** `converted library has no function
  'ls_Main_techWaterMain'` / `no stage-in library`: the tessellation VS is now
  converted library-only (the function is looked up by the object-shader name
  in winemetal) and always gets the input layout for its stage-in function.
* **Dark launcher.** The launcher is an ordinary GDI window (790x445
  StretchDIBits, `[winios] present hwnd=... surf=896x512`), and its bits did
  reach Winios -- but `ContentView.swift` never called
  `winios_set_game_layer` / `winios_set_game_rect` (upstream's Swift side of
  the direct-launch overlay was never merged), so the overlay host was never
  created: no `[overlay] created host=` line in any log. MetalBackedView now
  publishes the layer once and the game rect on every change (with the two
  relayout hooks). The launcher should show and take taps; the overlay also
  arms win32u's 16 ms message poll while it is visible. `MADEIRA_DIRECT_OVERLAY=0`
  turns the overlay off.
