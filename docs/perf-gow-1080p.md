# God of War at native 1920x1080: where the frame time goes

> **Türkçe özet:** 1080p'de oyun sırasında işlemci (CPU) neredeyse yalnızca
> verimlilik (E) çekirdeklerinde ve ~1.6 GHz'de çalışıyor; performans (P)
> çekirdekleri 1.31 GHz'e inip boşta kalıyor. Bu bir QoS hatası değil (oyun
> iş parçacıkları zaten USER_INTERACTIVE): çipin güç bütçesini GPU alıyor
> (720p'de P çekirdekleri kısmen geri geliyor, oyun durduğunda anında 3.5-4
> GHz'e çıkıyor). E çekirdekleri dolu, ortalama 6-8 iş parçacığı sırada
> bekliyor. Bu sıkışık CPU'nun ~%14'ünü wineserver yiyor: saniyede 10-16 bin
> istek, neredeyse tamamı oyunun iş sistemi semaforları (select +
> release_semaphore). "kernel32 içinde %43" bulgusu bir ölçüm yanılgısı:
> o iki çağrı Sleep ve GetCurrentThreadId; örnekler aslında sched_yield
> sırasında bekleyen iş parçacıklarını ve FEX'in güncellenmeyen RIP'ini
> sayıyor. GPU zamanı hiçbir logda yoktu; bu dal `[frame]` satırını ekliyor.
> **Yeni build gerekmeden denenebilecekler:** God of War oyun ayarına
> `inproc-sync = 1` (Madsync), `env.DXMT_LOG_LEVEL = none`, `env.WINEDEBUG`
> satırını kaldırmak, 1080p'de MetalFX kapalı. Ayrıntı ve test sırası bölüm
> 3.2 ve 4'te.

Measured on the owner's iPhone 17 Pro Max (A19 Pro, 2 P + 4 E cores, iOS
27), build 279, God of War (2018 PC, D3D11 through DXMT, committed 64-bit PE
`d3d11.dll`), fastsync (default sync engine), game config `dxmt =
d3d11.mipClampBC=2`, `swap-mb = 6144`, `swap-min-kb = 1024`,
`env.WINEDEBUG=err+all,err-virtual,fixme-all`, Memory pool off.

| Log | Setting |
|---|---|
| `GoW.exe-2026-10-01_15-06-44.txt` (main) | native 1920x1080, no MetalFX, ~3 min of gameplay outdoors (15:07:07-15:10:10) |
| `GoW.exe-2026-10-01_15-01-54.txt` | 1920x1080 + MetalFX 2x (output 3840x2160) |
| `GoW.exe-2026-10-01_14-51-20.txt`, `..._15-52-42.txt` (build 282) | 1280x720 comparisons |

Line numbers below are in the main log unless another log is named.
Analysis scripts (not committed): a per-window `[xp]` aggregator, a per-thread
`[xp-t]` aggregator, a PE import/export reader for GoW.exe and the shipped
`app/Madeira/arm64ec-windows/*.dll`, and a decoder for ARM64EC fast-forward
(FFS) thunks in `.hexpthk`.

## 1. What the logs show

### 1.1 The CPU runs on the efficiency cores: the SoC power budget, not QoS

`[xp]` per ~300 ms window, aggregated (cores = CPU ms / wall ms; runq = Mach
runnable time / wall, i.e. threads waiting for a core; W = process CPU energy):

| window | cores | P cores | E cores | runq | P GHz | E GHz | CPU W |
|---|---|---|---|---|---|---|---|
| 15:06:49-15:07:04 (load) | 3.0-4.0 | 1.0-2.0 | 0.2-2.2 | 1.4-7 | 2.7-3.5 | 2.6 | 2.3-3.9 |
| 15:07:07-15:10:10 (gameplay) | 3.3-3.7 | **0.0-0.9** | **2.5-3.6** | **5.6-8.0** | **1.31** | **1.6-1.7** | **0.45-0.8** |
| 15:10:12-15:10:33 (load drops) | 1.2-1.5 | 0.6-0.8 | 0.6-0.7 | 1.5-1.9 | **2.9-4.05** | 2.45 | 1.0-2.1 |

* The switch is abrupt: line 16781 (15:07:05.110) P=620 ms at 2.29 GHz;
  line 17354 (15:07:07.860) `P=0 E=1152 run=2670 ... GHz P=0.00 E=1.70
  mJ=182` -- 3.7 E-cores busy, 8.5 threads waiting, 0.58 W.
* 1080p + MetalFX 2x (15:01:54) is the same: P 0.1-0.4 cores at 1.31 GHz,
  E 2.3-3.2 cores at 1.5-1.7 GHz, runq ~7.
* 720p (14:51:20, 15:52:42) keeps 0.8-1.8 P-cores, still at 1.3-2.0 GHz.
* When the load drops (15:10:12, line 50964) the P-cores are back at once at
  **4.05 GHz**. So nothing caps the P-cluster permanently; the power controller
  gives the budget to whoever needs it, and during 1080p gameplay that is the
  GPU. The 720p menu HUD (GPU 21-22 ms/frame at 53-56 FPS, thermal Nominal,
  "Composited", 120 Hz) says the GPU is near 100 % busy already at 720p.
* QoS is not the cause: the guest main thread is USER_INTERACTIVE (`[main-qos]
  ... class now 0x21`, line 129), every guest thread starts at
  USER_INTERACTIVE (thread_ios.c start_thread -> ios_eco_apply_self), Windows
  priorities below the realtime band no longer demote them (`[thread-prio]
  ... kept at pthread QoS`, tools/patch-wine-thread-qos.py), and ECO was off
  (no `[eco]` line). Raising
  QoS further is not possible below the realtime band, and time-constraint
  (realtime) threads that overrun are demoted by the kernel -- not
  recommended. More P-core time can only come from a smaller GPU share or
  less CPU work.

### 1.2 Who uses the CPU (1080p gameplay, mean ms per ~300 ms window, 560 windows)

From `[xp-t]` 15:07:10-15:10:02 (tid -> name from `[thr-name]`):

| thread | ms/300 ms | share of one E-core |
|---|---|---|
| 0084 DxRenderThread | 179 | 60 % |
| **wineserver main loop** (native m1799377; `[thread-sample]` lr=main_loop/read_request, cpu 40-58 %) | **140** | **47 %** |
| 0024 main thread | 131 | 44 % |
| 0054/0058/005c/0060 TaskManager00-03 | 87 each (347) | 4 x 29 % |
| 0070 dxmt-encode-thr | 58 | 19 % |
| 00c0 (Wwise "AK" thread) | 48 | 16 % |
| everything else | < 16 each | |

Total ~1020 ms per 300 ms = 3.4 cores, all on 4 E-cores at ~1.6 GHz. The
workers spin before they sleep (GoW+0xb33b40: `lock cmpxchg` + `pause` loop on
a counter, then `WaitForSingleObject(semaphore, INFINITE)`; `[thread-sample]`
TaskManager00/01 RUN at GoW+0xb33b52), so slow wake-ups also cost spin time.

### 1.3 The wineserver: 10-16 thousand requests a second

* `[srv-req]` (lines 20915-48395): of every 200,000 requests, **req29 = select
  ~98,500** and **req41 = release_semaphore ~96,500**, the next one
  (event_op) ~2,000; 200,000 requests take 11.7-20.8 s.
* `[sync-census] ml1117 server requests 10,250-15,756/s` (line 22422 on).
  720p: 3,700-8,200/s. With madsync (log 2026-09-30 11:55): **249/s**.
* `[fastsync] mode=auto peek=on sem=off` (line 389): fastsync handles events
  but **not semaphores**, so the job system's every hand-off is a pipe round
  trip to the in-process server: write, server wake-up, reply, client wake-up.
* Alert (futex) wake latency on the saturated cluster: average 53-243 us,
  131-865 waits a period above 500 us (`[sync-census] ml1122`, line 17982 on).

### 1.4 "43 % inside two kernel32 calls" is a measurement artefact

The two IAT calls are named exactly (GoW.exe import table + shipped
`arm64ec-windows/kernel32.dll` exports):

| bucket | IAT slot | import | target |
|---|---|---|---|
| GoW+0x581100 | 0x140d48220 | KERNEL32!Sleep | kernel32+0x374f0 = `Sleep` |
| GoW+0x553f00 | 0x140d48448 | KERNEL32!GetCurrentThreadId | kernel32+0x409a0 = `GetCurrentThreadId`, an x64 FFS thunk in `.hexpthk` -> EC kernel32+0x26530 |
| GoW+0x9958c0 | 0x140d48440 | KERNEL32!QueryPerformanceCounter | kernel32+0x34740 |
| GoW+0xb33b80 | 0x140d48090 | KERNEL32!WaitForSingleObject | kernel32+0x34870 |
| GoW+0xb84180 | 0x140d480a8 | KERNEL32!LeaveCriticalSection | ntdll+0x91ce0 = `RtlLeaveCriticalSection` (FFS) |

But the profile does not mean the CPU is inside them:

* `RUNNING` is Mach `TH_STATE_RUNNING`: on a core **or queued for one**.
* The guest RIP read from the FEX frame is FEX's last synchronised RIP; it
  moves when the thread leaves the JIT (calls into ARM64EC code, dispatcher
  exits), not per x64 instruction. A bucket at an IAT call means "last left
  the JIT there".
* `[cpu-split]` of the same profiles: gen 6 (line 40386) Sleep bucket 51 %,
  but host pcs **86 % native, 271 of 315 samples in `swtch_pri`**
  (`macx_triggers+0x4`, x16 = -59, lr `cthread_yield`), ARM64EC images 1 %;
  gen 8 (line 50836) Sleep 26 % / GetCurrentThreadId 17 % while ARM64EC
  images are 2 % and `swtch_pri` 54 of 123.
* The Sleep caller is a polling loop (GoW+0x581120: `if (count == 0)
  Sleep(4)`). `NtDelayExecution` yields first (`NtYieldExecution` ->
  `sched_yield`), and on a saturated cluster a yielding thread is depressed
  and waits in the run queue -- runnable, not burning CPU. `[xp-api]`: delay
  ~200-240/s, all in the `<5ms` bucket = this one thread.
* GetCurrentThreadId is called by the main thread around GoW+0x553eb0 (a
  getter that compares the caller with the main thread id); each call is an
  x64 -> ARM64EC transition through the FFS thunk. How many per second is not
  in the log -- see 3.1 (b).

### 1.5 ~280 Mach exceptions a second redirect calls to PE addresses

`[xlate-exec]` (logged every 1024th, child process threads only) reaches
`#84992` at 15:10:34 (line 52745), ~280/s for the whole run. The four hot
targets were queued by `[stale-heal]` but it rewrote 0 slots (lines
1300-12193), because the pointers are computed, not stored: they come from
`GetProcAddress` and are called through `__os_arm64x_check_icall`, which
decodes the export's x64 fast-forward thunk to the EC function's **PE**
address, and PE pages are not executable here. Named from the shipped DLLs:

| fault pc | function | thread (sampled lines) | share |
|---|---|---|---|
| ntdll+0x6a744 | `__wine_dbg_output` (DXMT's logger) | DxRenderThread | ~50 % |
| kernelbase+0x68e28 | `WaitOnAddress` (libc++ `std::atomic::wait` in DXMT) | dxmt-encode/finish | ~25 % |
| ntdll+0x688a8 | `RtlWakeAddressAll` (`notify_all`) | DxRenderThread, encode | ~20 % |
| kernelbase+0x23d98 | `GetSystemTimePreciseAsFileTime` | TaskManager, main | ~5 % |

Each one stops its thread for an exception round trip through the handler
thread (tens of microseconds on an E-core).

### 1.6 Logging

~155 log lines/s in gameplay, ~130/s of them DXMT `err:` census lines
(`[bc-stream]` one per staging copy ~27/s, `[mem-census]`, `[dyn-census]`,
`[buf-site]`, `[trim]`, `[live]`): 34,946 DXMT lines in the session. DXMT
logs at Info level whatever WINEDEBUG says (`DXMT_LOG_LEVEL` unset), and each
line costs a `__wine_dbg_output` exec fault (1.5) plus a write, on the busiest
thread.

### 1.7 GPU

No frame or GPU timing was logged (the `[present]` FPS line needs the FPS
overlay; DXMT's per-present cadence log is muted by MADEIRA_QUIET). Known: the
720p menu HUD (GPU 20.8-22.3 ms/frame, 53-56 FPS, present delay ~28 ms =
~1.5 frames of queue, "Composited", RGB10A2, 120 Hz). Native 1080p has 2.25x
the pixels. MetalFX 2x at 1080p renders 1080p and **outputs 3840x2160**,
which the compositor then scales down to the 2868x1320 panel (a 16:9 image
fit to the panel is 2347x1320, i.e. a 1.22x upscale would already be
pixel-exact). The present delay is queueing (latency), not throughput.

## 2. Ranked bottlenecks

| # | bottleneck | evidence | size |
|---|---|---|---|
| 1 | SoC power budget: CPU on E-cores at 1.6 GHz, P parked at 1.31 GHz, run queue 6-8 | `[xp]` 17354, 31595; 50964 for the recovery | the whole CPU side; GPU near 100 % at 720p already |
| 2 | wineserver round trips for the job system's semaphores (fastsync has `sem=off`) | `[srv-req]`, `[sync-census] ml1117`, `[xp-t]` | ~47 % of an E-core on the server + 2 context switches per wait/wake; ~14 % of all CPU |
| 3 | spin-then-wait workers waking slowly | TaskManager 4 x 29 %; alert latency 53-243 us avg | game code; amplified by #1 and #2 |
| 4 | Mach exception redirects of GetProcAddress'd EC functions | `[xlate-exec]` #84992, `[stale-heal]` rewrote 0 | ~280/s, mostly on DxRenderThread / DXMT encode |
| 5 | DXMT logging at Info level | 34,946 `err:` lines, ~130/s | ~1-2 % of the render thread plus #4's ~50 % |
| 6 | x64 -> ARM64EC calls for trivial getters (GetCurrentThreadId, QPC) | 1.4 | unknown until `[xp-api]` counts them (3.1 b) |
| 7 | always-on profilers | thread sampler / RIP profile suspend threads; xprobe 4 Hz | < 1 % (estimate) |

GPU time itself is not ranked: there is no measurement yet; 3.1 (c) adds one.

## 3. Optimisations

### 3.1 Implemented in this branch (all diagnostics, or off by default)

| change | what | default / switch | risk for God of War |
|---|---|---|---|
| (a) `[rip-profile] ml1112b` | the IAT call lines name the callee from its export table and the slot from the caller's import table: `call [0x140d48220] -> 0x71fe7074f0 = kernel32.dll!Sleep (import KERNEL32.dll!Sleep)`; one note line explains RUNNING / stale RIP | always on (part of the existing profile) | none: read-only `vm_read_overwrite` into stack buffers, bounded loops, no allocation or lock, on the sampler thread (not a signal/exception context), <= 6 lookups per profile. Host-tested against GoW.exe and the shipped kernel32.dll |
| (b) `[xp-api] ml1131c` | without D3D12 role threads (every D3D11 game), the counters follow the Wine process with the most CPU in each 10 s window, so `[xp-api] x64->EC N/s`, `[xp-api-top]` (named x64->EC call targets, i.e. how often GoW calls GetCurrentThreadId/QPC/Sleep...), `[xp-api-qpc]` and `[xp-api-cs]` appear for God of War | always on (measurement only, xprobe thread); D3D12 roles still win | none for the game; a few more log lines per second |
| (c) `[frame]` instrument | the `ios_frame_*` hooks winemetal already calls (were empty stubs) now print once a second: presents/s, game Presents/s, **GPU busy** (union of command-buffer GPU start..end), ms/frame, command buffers, queue depth, nextDrawable wait, passes and attachments per frame, panel/limiter | **off**; `env.MADEIRA_FRAME_STATS = 1` | off: identical to before. On: one completion handler per command buffer + relaxed atomics, one line/s |
| (d) `tools/patch-winemetal-gpu-span.py` | completion handler also passes GPUStartTime/GPUEndTime to (c) | only runs with (c) on; CI step "Patch winemetal GPU timeline for [frame]" (native, not in the i386 farm key) | none when off |
| (e) `MADEIRA_PROBES` | `light`: only the 4 Hz xprobe (no thread is suspended); `0`: no profilers | unset = all, as before | none by default |

None of these makes the game faster by itself (expected gain 0; (e) saves
under 1 % of CPU on a timing run). They make the next log answer what the
current ones cannot: GPU busy per frame, and how often the game crosses into
ARM64EC code and for what. Switching off: (a) goes with the thread sampler
and (b) with the xprobe (`env.MADEIRA_PROBES = 0` stops both, `light` stops
(a)); (c)/(d) are off unless `env.MADEIRA_FRAME_STATS` is set.

### 3.2 Ready to test now -- existing switches, no build needed (ranked)

All go into God of War's own config (Library -> long press -> Game settings ->
"Advanced: this game's config"); remove a line to undo.

1. **`inproc-sync = 1` (Madsync for this game).** Madsync keeps semaphores,
   events and mutexes in-process (build/madsync/madsync.c was written for
   exactly this: "~18,000 requests a second, 2/3 of them select"). God of War
   ran on madsync until the round-3 merge (HANDOFF; build 243 log 11:55 ran
   with it, 249 server requests/s). Expected: the server thread's ~0.45 E-core
   freed and faster job wake-ups; on a CPU-starved cluster maybe 5-15 % FPS
   when the CPU is the limit. Risk: low-moderate (it is the previous default
   for this game). Undo: delete the line. Look for `[madsync] ... ENABLED`,
   `[fastsync] not started`, and `ml1117 server requests` in the hundreds.
   Alternative if madsync misbehaves: keep Fastsync and turn on the game's
   "Fast semaphore waits (experimental)" toggle (= `MADEIRA_FASTSYNC_SEM=1`;
   host model tests pass, never run on a device); look for `[fastsync] ...
   sem=on`.
2. **`env.DXMT_LOG_LEVEL = none`** and **delete the `env.WINEDEBUG=...`
   line**. Removes ~130 log lines/s and about half of the exception redirects
   (1.5), on the render thread. Expected 1-3 %. Risk: none for the game; the
   DXMT census lines (`[mem-census]` ...) disappear -- put the lines back for
   memory debugging. `env.DXMT_CENSUS_THROTTLE = 1` is the milder variant
   (census once per 10 s, other DXMT lines stay).
3. **MetalFX off at native 1080p** (or `metalfx-upscale = 1.2`, the factor
   that matches the panel). 2x renders 1080p and outputs 3840x2160 for a
   2868x1320 panel. Expected: a few % of GPU time (not measured).
4. **`env.DXMT_WAIT_ON_ADDRESS = 1`.** In the committed 64-bit d3d11.dll
   (string `[dxmt-wait] backend=wait-on-address` is there): DXMT's pipeline
   waits on the object's own word through ntdll's RtlWaitOnAddress/
   RtlWakeAddress* (direct imports) instead of libc++'s `std::atomic::wait`,
   which resolves WaitOnAddress by GetProcAddress (the ~45 % of exception
   redirects that are WaitOnAddress/RtlWakeAddressAll), hashes into a global
   256-slot table (unrelated wakes) and reads the clock twice per backoff.
   On by default in the 32-bit (i386) build; off for 64-bit.
   Expected 1-3 % and smoother pacing. Risk: moderate (new on 64-bit). Undo:
   delete the line. Look for `[dxmt-wait] backend=wait-on-address`.
5. **`env.MADEIRA_LD_BOUNDS = 0`** at native 1080p only: the texture-load and
   typed-UAV-store range checks (builds 282/284) were added for the darkening
   below 1080p, which does not happen at native 1080p; they add ALU to every
   `ld`. Expected: small GPU gain (0-3 %, not measured). The first launch
   re-converts every shader (different cache salt). Risk: none at 1080p;
   keep it on (delete the line) for lower internal resolutions.
6. **In-game graphics settings.** The GPU takes the power budget (1.1), so
   every GPU millisecond saved also returns CPU clock. Shadows, reflections,
   atmospherics, ambient occlusion and anisotropic filtering are the usual
   heavy ones on a mobile GPU. The owner's choice; measure with `[frame]`.
7. **`env.MADEIRA_PROBES = light`** for timing runs (needs this branch's
   build). Keeps `[xp]`.

### 3.3 Proposed code changes (not implemented)

| # | change | expected | risk | where |
|---|---|---|---|---|
| a | `arm64x_check_call` (PE ntdll, signal_arm64ec.c): translate the EC target decoded from an FFS thunk to its JIT-pool copy on iOS, as the IAT sync does for import slots | removes ~280 exception round trips/s in GoW (every GetProcAddress'd EC call in every game) | moderate; the PE ntdll is a committed upstream binary, so this is an upstream change | wine dlls/ntdll (Will) |
| b | after `[xp-api-top]` shows the rate: a fast path for trivial x64 getters (GetCurrentThreadId/ProcessId, TlsGetValue) -- FEX could recognise the FFS thunk targets and inline `mov eax, gs:[0x48]` | unknown (rate unknown) | moderate | FEX |
| c | `NtDelayExecution`: no leading `NtYieldExecution` for timeouts >= 1 ms (a depressed yield on a saturated cluster turns `Sleep(4)` into 4 + up to ~10 ms) | latency of polling threads; CPU ~0 | low, behind a switch (tools/patch-wine-*.py) | wine sync.c |
| d | `framebufferOnly = true` on iOS when neither MetalFX nor frame generation is on (DXMT sets false: "how strangely setting it true results in worse performance" -- a macOS observation) | GPU bandwidth of the present pass, small | low, switchable native winemetal patch; verify with `[frame]` | winemetal |
| e | if `[frame]` shows GPU busy ~100 %: GPU work reduction in airconv/winemetal guided by the pass counts (render passes, loads/stores per frame) | depends on data | -- | airconv / winemetal |

## 4. What the owner should test (build with this branch)

Same spot outdoors, native 1920x1080, MetalFX off, 3-5 minutes each, one change
at a time; keep a Metal HUD screenshot of each run.

0. Global madeira.cfg (Settings -> All settings): `env.MADEIRA_DEVICE_STATS =
   1` (thermal state and Low Power Mode every 10 s, `[device-load]`).
1. Baseline: God of War config + `env.MADEIRA_FRAME_STATS = 1`.
2. + `inproc-sync = 1`.
3. + `env.DXMT_LOG_LEVEL = none`, without the `env.WINEDEBUG=...` line.
4. + `env.DXMT_WAIT_ON_ADDRESS = 1`.
5. + `env.MADEIRA_LD_BOUNDS = 0` (wait at the menu until shader compilation
   settles the first time).

Send the whole session log of each run. The lines that matter:
`[frame]` (FPS, GPU busy %, ms/frame, nextDrawable wait), `[xp]` / `[xp-t]`
(P/E split, GHz, run queue), `[xp-api]` / `[xp-api-top]` / `[xp-api-qpc]` /
`[xp-api-cs]` (x64->EC calls by name), `[sync-census] ml1117` and `[srv-req]`
(server load), `[rip-profile] ml1112 bucket ... = module!export`,
`[xlate-exec]` (counter), `[device-load]`, `[madsync]` / `[fastsync]`,
`[dxmt-wait]`. Fallback: remove the added lines (build 286 behaviour).

Reading `[frame]`: GPU busy near 100 % = GPU-bound (lower GPU settings / no
MetalFX help most); a large nextDrawable wait = the display holds the frame;
neither, with `[xp]` runq high = CPU-bound (steps 2-4 help most).
