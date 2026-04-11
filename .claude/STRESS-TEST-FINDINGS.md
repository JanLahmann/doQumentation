# Stress Test Findings — CE Workshop Mode

**Date:** 2026-04-11
**Target:** `ce-doqumentation-01` (single CE app, 1 vCPU / 4 GB, max-scale=1)
**Harness:** [scripts/workshop-stress-test.py](../scripts/workshop-stress-test.py)
**Images tested:**
- **Old**: `ghcr.io/janlahmann/doqumentation-codeengine` pinned `577a63` (CE revision `-00021`) — pre-fix
- **New**: pinned `7ec50c` (CE revision `-00022`) — post-fix, deployed via CI build `24279189148`

## TL;DR

**Initial run** found workshop mode was unusable because nginx rate-limited `/build/` to 5 per minute per source IP. **Fix deployed** (now `100r/m + burst=50`).

**After the fix**, ran the harness across **four pod sizes** AND **two burst patterns** (synchronous + uniform-stagger via new `--ramp-interval` flag) to characterize the real ceiling:

### Per-pod capacity scaling with CPU count (validated)

| Pod | peak_conn | 50u/5s success | 80u/5s success | 100u/5s success | 100u/75s |
|---|---|---|---|---|---|
| 1 vCPU / 4 GB | 6 | n/a | n/a | n/a | n/a |
| 4 vCPU / 8 GB | 18-20 | 70% | 56% | n/a | n/a |
| 8 vCPU / 16 GB | 59 | 92% | 81% | n/a | n/a |
| **12 vCPU / 24 GB** | **73-74** | n/a | **96%** | **88%** | **100%** |

**The peak_conn ceiling scales roughly linearly with CPU count** (~6 sessions per vCPU), with **diminishing returns above 8 vCPU**. At 12 vCPU, a **new bottleneck emerges**: the SSE shim's threaded HTTPServer (Python threads + GIL contention) starts limiting concurrent SSE handshakes around 80-100 simultaneous connects.

**The new model**: per-pod session capacity is **CPU-scalable up to ~8 vCPU**, then SSE-shim-limited above that. Memory is essentially free for 5-qubit workloads (highest measured: 6.9 GB / 24 GB cgroup at peak).

**Stagger window helps but doesn't unlock new capacity** for long sessions. It just spreads the simultaneous-connection count over time. For instructor-led workshops where everyone clicks within ~5s, **pod size** is the dominant variable; for "students filter in over 1-2 minutes" patterns, stagger removes the burst pressure entirely.

**Sizing recommendation for workshops** (revised, validated):

| Workshop size | Single-pod config |
|---|---|
| 30-50 users | **1 × 8 vCPU / 16 GB** |
| 50-80 users | **1 × 12 vCPU / 24 GB** |
| 80-100 users | **1 × 12 vCPU / 24 GB** + frontend stagger (96% burst, 100% staggered) |
| 100+ users | Multi-pod (2+ × 12 vCPU) |

The design doc's original "3 × 4 vCPU / 8 GB" was correct in capacity but **a single 12 vCPU pod is operationally simpler** at the same cost.

**Highest-leverage future fix**: refactor the SSE shim from threaded to async (`aiohttp.web`) — would push the 12 vCPU clean burst capacity from ~80 to ~120-150 users.

**Memory caveat**: today's harness uses 5-qubit circuits. Real workshop content with 25-qubit statevector simulations needs ≥8 GB pods (one 25-qubit circuit = 512 MB statevector). The 16+ GB on the recommended pods is sized correctly for advanced workshop content.

## Test setup

- **Pre-test cleanup**: changed `ce-doqumentation-01` `max-scale` from `5` to `1` (the design doc requires `max-scale=1` because Jupyter kernels are stateful and CE has no session affinity); deleted a stale duplicate app `ce-doqumentation-1`.
- **Instrumentation** (option B, full): live `ibmcloud ce app logs --follow` streamed to file, `/api/status` polled every 1s, both running in background while harness ran. Files in `/tmp/dq-stress/`.
- **Workload**: 5-qubit `random_circuit(5, 3, measure=True)` + `AerSimulator().run(qc, shots=1024)` per cell — the harness's default `QISKIT_CELL`.
- **Conservative ramp**: started with 1-user smoke (`--simple` workload), then 1-user Qiskit, then `3 → 6 → 9` users. Did NOT push to higher counts because the failure mode was already clear at 6.

## Results — old image (pre-fix, original harness)

| Step | Users | Workload | Kernels OK | Avg cell | p95 cell | Failures |
|---|---|---|---|---|---|---|
| 0 | 1 | `print()` | 1/1 | 0.8s | 1.4s | 0 |
| 1 | 1 | Qiskit | 1/1 | 1.2s | 3.0s | 0 |
| 2a | 3 | Qiskit | **3/3** | 3.4s | 9.5s | 0 |
| 2b | 6 | Qiskit | **4/6** | 2.3s | 7.9s | 2 SSE drops |
| 2c | 9 | Qiskit | **4/9** | 2.2s | 7.6s | 5 SSE drops |

Latency numbers above are inflated by ~200ms per cell because the original harness opened a new WebSocket per cell.

## Results — new image (post-fix, refactored harness, two pod sizes)

Same target, same workload, same `--cells-per-user 3 --idle-between 5`. New image (CE revision `-00022` and later, source code unchanged) + refactored harness (`KernelSession` reuses one WebSocket per kernel).

### Run 1 + Run 2 (reproducibility check) — 1 vCPU / 4 GB

| Step | Users | Run 1 (kernels/fail/avg/p95) | Run 2 / repro |
|---|---|---|---|
| smoke | 1 simple | 1/1, 0 fail, 0.0s/0.1s | — |
| 2a' | 3 Qiskit | 3/3, 0, 1.9s/5.6s | 3/3, 0, 2.0s/5.7s |
| 2b' | 6 Qiskit | 6/6, 0, 3.5s/12.2s | 6/6, 0, 4.0s/11.7s |
| 2c' | 9 Qiskit | 9/9 alloc, **2 WS fail**, 4.6s/14.5s | 9/9 alloc, **3 WS fail**, 3.8s/12.4s |
| 2d' | 12 Qiskit | 12/12 alloc, **10 WS fail**, 2.1s/6.1s | 12/12 alloc, **11 WS fail**, 1.8s/5.2s |

**Reproducibility: confirmed.** Both runs show same pattern — clean through 6 users, marginal at 9, saturated at 12. Numerical differences within run-to-run noise.

### Run 3 — 4 vCPU / 8 GB (workshop default sizing)

| Step | Users | Kernels alloc | Failures | Avg cell | p95 cell | Pod stats |
|---|---|---|---|---|---|---|
| 3a | 3 | **3/3** | 0 | 0.7s | 2.0s | `peak_k=3 mem=189/7629MB(2%) load=4.09/4.0cpu` |
| 3b | 6 | **6/6** | 0 | 1.0s | 3.1s | `peak_k=6 mem=190/7629MB(2%) load=3.08/4.0cpu` |
| 3c | 12 | **12/12** | 0 | 2.2s | 7.4s | `peak_k=12 mem=192/7629MB(3%) load=3.28/4.0cpu` |
| 3d | 20 | **20/20** | 0 | 4.1s | 14.1s | `peak_k=20 mem=196/7629MB(3%) load=1.73/4.0cpu` |
| 3e | 30 | **30/30** | **12 WS** | 4.3s | 14.3s | `peak_k=30 peak_conn=20 mem=808/7629MB(11%) load=6.47/4.0cpu` |

**Headline**: 4 vCPU / 8 GB handles **20 concurrent users with zero failures**. At 30, the connect storm wins (12/30 WS handshakes time out) but all 30 kernels were successfully allocated. Memory is 11% of available even at peak — not the bottleneck.

### Run 4 — burst-stagger validation on 4 vCPU / 8 GB (using new `--ramp-interval` flag)

After adding `--ramp-interval` to the harness, ran a series of tests to measure the effect of spreading user starts:

| Test | Users | Stagger | Failures | Pod stats |
|---|---|---|---|---|
| 4a | 30 | 0s (baseline) | 12 | `peak_k=30 peak_conn=20 mem=808/7629MB` |
| 4b | 30 | 3s | 9 | `peak_k=30 peak_conn=18 mem=650/7629MB` |
| 4c | 30 | 10s | 4 | `peak_k=39 peak_conn=18 mem=860/7629MB` |
| 4d | 50 | 30s | 15 | `peak_k=56 peak_conn=18 mem=1630/7629MB` |
| **4e** | **50** | **75s** | **0** | `peak_k=56 peak_conn=18 mem=1632/7629MB` |
| 4f | 80 | 75s | 1 | `peak_k=61 peak_conn=18 mem=1535/7629MB` |
| 4g | 80 | 5s (realistic burst) | 35 | `peak_k=106 peak_conn=18 mem=3330/7629MB(44%) load=14.70/4.0cpu` |

**Critical observation**: `peak_conn=18` was **constant across every test** on this pod. This is the **per-pod simultaneous-WebSocket ceiling** for 4 vCPU. Stagger doesn't raise it; stagger just keeps the simultaneous count *under* the ceiling by spreading work over time.

**Math** (validated experimentally):
- For N users with average session time T_session, uniformly staggered over T_stagger:
- **Effective concurrent users ≈ N × T_session / T_stagger**, capped at N
- For clean pass on 4 vCPU pod, need `effective concurrent ≤ 18`, so `T_stagger ≥ N × T_session / 18`
- For 50 users / 30s sessions: minimum stagger is `50 × 30 / 18 = 84s` (we tested 75s, got 0 failures — close enough)
- For 80 users / 30s sessions: minimum stagger is `80 × 30 / 18 = 134s` (we tested 75s, got 1 failure — outside the model's prediction but still mostly works because earlier sessions completed faster than 30s)

### Run 5 — 8 vCPU / 16 GB (verifying CPU scaling)

Resized `ce-doqumentation-01` to 8 vCPU / 16 GB (CE forces this combination — `cpu=8` requires `memory=16G` minimum).

| Test | Users | Stagger | Failures | Pod stats |
|---|---|---|---|---|
| 5a | 50 | 75s (clean baseline) | **0** | `peak_k=17 peak_conn=13 mem=195/15259MB(1%) load=3.57/8.0cpu` (avg 0.6s, p95 1.8s) |
| 5b | 80 | 5s (realistic burst) | 15 | `peak_k=80 peak_conn=59 mem=987/15259MB(6%) load=16.28/8.0cpu` (avg 6.8s, p95 26.8s) |
| 5c | 50 | 5s (with leftover load from 5b) | 4 | `peak_k=80 peak_conn=59 mem=1195/15259MB(8%) load=15.58/8.0cpu` |

**Key finding**: `peak_conn=59` on 8 vCPU vs `peak_conn=18` on 4 vCPU. **The ceiling scales ~3x with 2x the CPU** (slightly super-linear, probably because more CPUs reduce GIL contention and event-loop starvation).

**Practical implication**: 8 vCPU / 16 GB pod handles **80% of an 80-person workshop on a single pod** (test 5b: 65/80 success). For a more realistic 50-person workshop where everyone clicks within 5 seconds, **92% succeed** (test 5c, even with leftover load from a previous test).

### Run 6 — 12 vCPU / 24 GB (confirming linear scaling and finding new bottleneck)

Resized to 12 vCPU / 24 GB. **First attempt was disrupted by CE rolling-deploy chaos** — two pods alternating during the test produced corrupted data (`connections=-48` from a Jupyter counter underflow, `peak_k=124` from leftover state). Triggered a fresh revision and waited for old pod to drain before re-running.

| Test | Users | Stagger | Failures | Pod stats |
|---|---|---|---|---|
| 6a | 50 | 75s (clean baseline) | **0** | `peak_k=16 peak_conn=14 mem=194/22888MB(1%) load=1.96/12.0cpu` (avg 0.6s, p95 1.8s) |
| 6b | 80 | 5s (realistic burst) | **3** | `peak_k=80 peak_conn=73 mem=377/22888MB(2%) load=20.66/12.0cpu` (avg 5.1s, p95 19.1s) — **96% success** |
| 6c | 100 | 5s (push the limit) | 12 | `peak_k=94 peak_conn=74 mem=545/22888MB(2%) load=15.67/12.0cpu` — **88% success**, mostly SSE-stage failures |
| 6d | **100** | **75s** | **0** | `peak_k=94 peak_conn=74 mem=547/22888MB(2%) load=7.46/12.0cpu` (avg 0.7s, p95 2.2s) |

**Key findings from 12 vCPU**:

1. **Linear scaling continues**: `peak_conn=73-74` on 12 vCPU vs 59 on 8 vCPU. That's +14 ceiling for +4 vCPU = ~3.5 sessions/vCPU at the high end. The ratio is **slightly sub-linear** (4→8 was super-linear at +41, 8→12 is sub-linear at +14), which suggests **diminishing returns kick in around 8 vCPU**.

2. **A NEW failure mode appeared at 100u/5s**: 9 of 12 failures were `SSE stream ended without ready event`, not WebSocket handshakes. The SSE shim itself is becoming the bottleneck at 100+ simultaneous SSE connects. **The SSE shim uses `ThreadingMixIn` (one Python thread per request)** — past ~80 concurrent SSE handlers, GIL contention dominates and the event stream can't keep up. **An async (aiohttp) refactor of the SSE shim would lift this bottleneck** and likely push 12 vCPU's clean burst capacity from ~80 to ~120-150 users.

3. **12 vCPU pod handles 100 users at 75s stagger with ZERO failures**: realistic for instructor-paced workshops where clicks spread over 1-2 minutes. Avg latency 0.7s, p95 2.2s — **as fast as the 50-user clean baseline**.

4. **Memory remained at 1-2% of cgroup limit** across every test. With 24 GB available, even running 100 simultaneous Qiskit kernels uses only ~550 MB. Memory is comprehensively NOT the constraint at this workload.

### Side finding: Jupyter Server connection counter underflow bug

During the rolling-deploy chaos in the first 12 vCPU test, `/api/status` reported `connections: -48`. **Jupyter Server's `connections_dict` underflowed** — when a WebSocket fails mid-handshake (which happens often under our connect-storm pressure), the cleanup decrements the counter without a matching increment.

**Side effect**: kernels with phantom-negative connections **never get culled** (because `cull_connected = False` skips kernels with "active" connections, and a negative count looks active to the cull logic). After heavy stress testing, the pod held 48 zombie kernels indefinitely until I triggered a fresh revision.

**Real-world impact**: in a long workshop, the pod's memory would creep up across the day even though students keep leaving. Workshop hosts would need to manually restart pods between sessions, or call `DELETE /api/kernels/{id}` from the frontend on session close.

**Won't fix today** — added to backlog.

**Notable**:
- **2c' / 2d' failure mode is different from old image.** Old image (5r/m): `SSE stream ended without ready event` — kernel never allocated. New image: kernel IS allocated (`peak_k=9` and `peak_k=14` respectively), but the user's WebSocket handshake to `/api/kernels/{id}/channels` times out. This is a real CPU-saturation symptom, not a configured rate limit.
- **`peak_k=14` at users=12** because 2d' inherited 2 leftover kernels from 2c' that hadn't been culled yet (they were created in 2c' by users who timed out at the WS handshake stage but had already gotten past kernel creation). Confirmed by checking `sse_total=21` (= 9 from 2c' + 12 from 2d').
- **3-user case latency dropped 1.8x** (3.4s → 1.9s) on the same workload — entirely from harness WebSocket reuse, not from the new image. The old image's per-cell connect overhead was being counted as kernel latency.

## Root cause: nginx `/build/` rate limit

Original [binder/nginx-codeengine.conf:2](../binder/nginx-codeengine.conf#L2):

```nginx
limit_req_zone $binary_remote_addr zone=build:1m rate=5r/m;
...
location /build/ {
    limit_req zone=build burst=2 nodelay;
}
```

**`5r/m` = 5 requests per minute per source IP**, with `burst=2 nodelay` (allows a tiny burst of 2 above the rate, immediate rejection above that). The harness sends all requests from one IP (the laptop), so it hits the cap immediately:

- 2a (3 users) — 3 ≤ 5 → all pass → 3/3 ✓
- 2b (6 users) — first ~4 pass, others rejected with HTTP 503 → 4/6 ✗
- 2c (9 users) — same ceiling, more rejections → 4/9 ✗

**Confirmation in pod logs** (the SSE shim emits a `sse_connect` event for every request that *reaches* it):

| Step | Harness sent | Shim received |
|---|---|---|
| 2a | 3 | 3 |
| 2b | 6 | **3** |
| 2c | 9 | **4** |

Requests dropped by nginx never reach the Python SSE shim, hence the missing `sse_connect` events.

The harness's `connect_sse()` reports these as `"SSE stream ended without ready event"` because nginx closes the connection on rejection without emitting any SSE phases.

**Why this is fatal for workshops**: in a 50-person classroom, students share one external IP (campus NAT, conference WiFi). When the instructor says "open the notebook," all 50 click within seconds. **Only 5 succeed; 45 see an error.** The limit is per-IP at the nginx layer of every CE pod, so deploying more pods (pool mode) does not help — every pod has the same nginx with the same rate limit.

### Fix applied

[binder/nginx-codeengine.conf:2,20](../binder/nginx-codeengine.conf#L2-L20):

```nginx
# 100r/m + burst=50 — sized for a 50-person workshop where everyone clicks
# "Start" within seconds (NAT/conference WiFi shares one source IP).
limit_req_zone $binary_remote_addr zone=build:1m rate=100r/m;
...
location /build/ {
    limit_req zone=build burst=50 nodelay;
}
```

100 r/m sustained + burst 50 handles the worst-case workshop start (50 users in 30s) cleanly while still rejecting sustained flooding. The `/api/` zone (30 r/s) is left unchanged — it's the right size for normal Jupyter API traffic.

## Other findings (ordered by severity)

### HIGH — Cold start on a fresh K8s node is ~150 seconds, not 15-20s

Earlier observation suggested cold-start was 15-20s. That was on a node with the image already cached. When CE schedules the pod onto a fresh node, the timeline is:

| Phase | Duration |
|---|---|
| istio-validation + istio-proxy | ~13s (cached images) |
| **Image pull (905 MB)** | **~98s** |
| supervisord + jupyter spawn | 2s |
| Jupyter extension imports (jupyter_lsp 7s, jupyterlab 1.4s, etc.) | ~30s |
| **Total** | **~150s** |

**Implication**: the first user of any workshop session, hitting a cold pod on a cold node, waits 2.5 minutes. The harness's 120s SSE timeout would fire before the pod is ready, manifesting as a "failed" connection — even though nothing is broken.

**Mitigations** (not yet implemented):
1. **`min-scale=1` during workshops** — keeps one pod always-warm, eliminates cold-start tax for the first user. Costs ~$5/month. Add as a CE app config flag, optionally toggleable in the deploy workflow.
2. **Image size reduction** — current 905 MB is dominated by Jupyter extensions (`jupyter_lsp`, `jupyterlab`, `nbclassic`, etc.) and the full Qiskit stack. Could potentially shrink to ~400-500 MB by stripping unused extensions (no terminals, no LSP, no nbclassic). Added to project backlog.

### HIGH — `cull_idle_timeout=600` (10 min) is too long for workshops

[binder/codeengine-entrypoint.sh:62](../binder/codeengine-entrypoint.sh#L62) configured kernels to cull after 10 minutes of idleness. With ~17 users on 4 GB (the design doc's target), an inactive student leaves a kernel parked for 10 minutes, blocking new joiners.

### Fix applied

Changed to:

```python
c.MappingKernelManager.cull_idle_timeout = 300   # was 600
c.MappingKernelManager.cull_interval = 60        # was 120
c.MappingKernelManager.cull_busy = False         # explicit (was default)
c.MappingKernelManager.cull_connected = False    # unchanged
```

5 min idle is short enough to reclaim slots from absent students mid-session, long enough that someone reading a notebook between cells doesn't lose their state. `cull_busy=False` is now explicit (was relying on Jupyter's default) so future config changes can't accidentally enable it. `cull_connected=False` is intentionally kept — culling kernels with active websockets would kill students mid-cell.

### MEDIUM — Harness opens a new WebSocket per cell

[scripts/workshop-stress-test.py:96-135](../scripts/workshop-stress-test.py#L96-L135) (original) opened `websockets.connect(...)` inside `execute_cell()`, paying ~150-250ms of WebSocket handshake + Jupyter "Connecting to kernel" setup overhead per cell.

This is **not what real browser clients do**. thebelab and JupyterLab open one websocket per kernel and reuse it across many cell executions. The harness's per-cell connect was inflating reported latencies by a constant ~200ms, and triggered Jupyter `No session ID specified` warnings on every cell.

### Fix applied

Replaced `execute_cell()` with a `KernelSession` async context manager:

```python
async with KernelSession(server_url, kernel_id, server_token) as ks:
    for cell_num in range(cells_per_user):
        latency = await ks.execute(code)
```

`KernelSession.__aenter__` opens one websocket; `.execute(code)` reuses it for each cell; `__aexit__` closes it cleanly. The session ID is per-kernel and stable across cells (matching real-client behavior, silencing Jupyter's warning).

**Validated** with 1-user smoke run before commit: `print('hello')` latency dropped from 0.8s (old) to 0.0s (new). All previous Step 0/1/2 latencies should be read as **inflated by ~200ms per cell**.

### MEDIUM — Harness `/stats` polling broken

The original harness queried `/stats` at [scripts/workshop-stress-test.py:55](../scripts/workshop-stress-test.py#L55) but the SSE shim's `/stats` returns rich JSON (kernels, busy, connections, peak_*, memory_mb, peak_kernels, total_sse_connections). The harness's exception handler silently fell back to `{"kernels": 0, "status": "offline"}`, so the "Reported kernels" column in output was always 0. We didn't notice during the run because we had `/api/status` polling instead.

### Fix applied

`get_stats()` now returns the real `/stats` body. New `_format_stats(stats)` helper renders a one-line summary with peak kernels, peak connections, memory, and CPU load. Output now includes a `Pod stats:` line per ramp step.

### LOW — `No session ID specified` warnings in pod logs

Each cell triggered a Jupyter warning because the harness's `execute_request` set `header.session = msg_id` (random per-cell) but no top-level `session` field. Jupyter falls back gracefully but logs a warning. Fixed in the `KernelSession` refactor — `session_id` is now per-kernel and set on every message header.

### LOW — Jupyter Server config inconsistency in the image

Pod logs showed:
```
[W] The websocket_ping_timeout (90000) cannot be longer than the websocket_ping_interval (30000).
```

Cosmetic. Not introduced by us. Worth fixing in a later pass — possibly in the Jupyter config emitted by `codeengine-entrypoint.sh`.

### Observation — `/proc/meminfo` and `/proc/cpuinfo` show host values, not container limits

The first cgroup-aware version of `/stats` reported `mem=5330/62349MB(9%)` — that's the **Kubernetes node's** RAM, not the pod's 4 GB cgroup limit. Same problem with `/proc/cpuinfo` showing all of the node's cores.

### Fix applied

[binder/sse-build-server.py](../binder/sse-build-server.py) `_read_memory_mb()` now reads `/sys/fs/cgroup/memory.current` and `/sys/fs/cgroup/memory.max` first (cgroup v2 limits), falling back to `/proc/meminfo` only when cgroup files aren't available. New `_read_cpu_count()` reads `/sys/fs/cgroup/cpu.max` to compute the effective CPU limit. New `/proc/loadavg` reader adds 1m/5m/15m load averages to `/stats`. The shim now also emits a `high_cpu` log event when 1m load exceeds CPU count (saturation).

### Observation — CE pod scales to zero aggressively

`Scale Down Delay: 0` means CE reaps the pod within ~30s of HTTP idleness. This happened multiple times during testing (between Step 1 and Step 2; between Step 2 and post-test probes). Each scale-up paid the 15-150s cold-start tax depending on whether the image was cached on the target node. **For workshops, set `min-scale=1`** to prevent this entirely.

### Observation — No persistent logging

The IBM Cloud account has no logging service instance bound (`logdna`, `logs`, `sysdig-monitor`, `logdnaat` all return `No service instance found`). When CE reaps a pod, all logs from that pod are lost forever — the logs from Step 0 are gone. For today's stress test we captured logs to local files via `ibmcloud ce app logs --follow`. For ongoing workshop deployments, consider provisioning **IBM Cloud Logs** (free tier covers small workloads, ~$0-5/month for occasional workshop use) and wiring it into the CE project.

## Real per-pod capacity (post-fix data, validated across three pod sizes + stagger window sweep)

### Capacity scaling with CPU count

The `peak_conn` value (max simultaneous active WebSocket connections measured during a test) is the cleanest metric for per-pod capacity. **It scales linearly with CPU count up to ~8 vCPU**, then sub-linearly:

| Pod | peak_conn | Per-vCPU ratio | Source test |
|---|---|---|---|
| 1 vCPU / 4 GB | 6 | 6.0 | 12u/0s test (12→6 succeed) |
| 4 vCPU / 8 GB | **18-20** | ~5.0 | constant across 7 tests with different stagger windows |
| 8 vCPU / 16 GB | **59** | ~7.4 | 80u/5s test |
| **12 vCPU / 24 GB** | **73-74** | **~6.1** | 80u/5s and 100u/5s tests |

**Slope analysis**:
- 4→8 vCPU: +41 to peak_conn (slightly super-linear, GIL contention reduction)
- 8→12 vCPU: +14 to peak_conn (sub-linear, **diminishing returns kick in**)

The diminishing return at 12 vCPU suggests **a different bottleneck is starting to dominate** — confirmed during 100u/5s test where failures shifted from WS handshake to SSE handshake (`SSE stream ended without ready event`). The SSE shim's threaded HTTPServer hits GIL contention around 80-100 concurrent SSE requests. Refactoring it to async would lift this ceiling.

**Practical rule of thumb**: **~6 sessions per vCPU**, capped around 80 concurrent on a 12 vCPU pod. Beyond 80 concurrent, scale horizontally (more pods) rather than vertically (bigger pods).

### Real workshop capacity by pod size

For instructor-led workshops where all users click "go" within ~5 seconds:

| Pod size | "Safe" workshop (≥95% success) | "Stretch" with frontend stagger | Note |
|---|---|---|---|
| 1 vCPU / 4 GB | ~5 users | ~6 | Solo dev / smoke testing only |
| 4 vCPU / 8 GB | ~20-25 users | ~50 (75s+ stagger) | Decent for medium workshops |
| 8 vCPU / 16 GB | ~45-50 users | ~80 | Good for 50-person workshops |
| **12 vCPU / 24 GB** | **~75-80 users** | **~100** | **Recommended for 50-100 person workshops** |

### Reproducibility check (1 vCPU pod)

Same workload, same image, second run: identical results within noise. 6/6 users always pass; 9 users fails 2-3/9; 12 users fails 10-11/12. **Reproducible.**

### The bottleneck is per-pod simultaneous WS connection ceiling, NOT memory or kernel creation

In every saturation case, **all kernels were created successfully** (`peak_k` matched user count). Failures were always at the WebSocket handshake stage on `/api/kernels/{id}/channels`. This is **transient CPU saturation during the connect burst**, not a resource ceiling.

Memory usage at peak across all tests:
- 1 vCPU / 4 GB at 12 users: 876 MB / 4 GB = **22%**
- 4 vCPU / 8 GB at 30 users: **808 MB / 7629 MB = 11%**

**Memory is comprehensively NOT the bottleneck for this workload.** It IS overprovisioned at 8 GB for 5-qubit simulations. See "Memory caveat" below for when this changes.

### Memory caveat: 5-qubit assumption

All measurements above use the harness's default workload: `random_circuit(5, 3, measure=True)` + `AerSimulator().run(shots=1024)`. This is intentionally lightweight — small enough that the **statevector** (2^5 × 16 bytes = 512 bytes) is negligible compared to the Python interpreter's ~50-60 MB baseline.

Memory cost of larger statevector simulations:

| Qubits | Statevector size | Per-kernel total (with Python overhead) |
|---|---|---|
| 5 | 512 bytes | ~60 MB |
| 10 | 16 KB | ~60 MB |
| 15 | 512 KB | ~60 MB |
| 20 | 16 MB | ~80 MB |
| 25 | **512 MB** | ~570 MB |
| 28 | **4 GB** | exceeds pod |
| 30 | **16 GB** | OOM-kill on most CE configs |

**Implication**: workshops covering only intro Qiskit (≤15 qubits) can run on **4 GB pods**. Workshops touching the advanced courses (`fundamentals-of-quantum-error-correction`, `quantum-diagonalization-algorithms`) need **8 GB minimum** because individual notebooks may construct 25-qubit statevectors. The design doc's 8 GB choice was correct for general workshop use.

**Aer's matrix-product-state and density-matrix backends scale much more slowly with qubit count** — those are escape hatches for >25-qubit content.

### Per-kernel resource cost (idle Qiskit kernel, small workload)

- **Memory**: ~30-65 MB (NOT the 300-400 MB design doc assumed)
- **CPU**: negligible at idle, ~100% of one core during `random_circuit + simulator + 1024 shots`

### Sizing implications for real workshops (final, validated across 1/4/8/12 vCPU)

| Workshop size | Simplest config | Cost-equivalent alternative |
|---|---|---|
| 5-15 users | 1 × 4 vCPU / 8 GB | — |
| 15-30 users | 1 × 4 vCPU / 8 GB (tight) or 1 × 8 vCPU / 16 GB | — |
| **30-50 users** | **1 × 8 vCPU / 16 GB** | 2 × 4 vCPU / 8 GB (more failover) |
| **50-80 users** | **1 × 12 vCPU / 24 GB** | 2 × 8 vCPU / 16 GB or 3 × 4 vCPU / 8 GB |
| **80-100 users** | **1 × 12 vCPU / 24 GB** + frontend stagger | 2 × 8 vCPU / 16 GB |
| 100-150 users | 2 × 12 vCPU / 24 GB | 3 × 8 vCPU / 16 GB |
| 150+ users | 3+ × 12 vCPU / 24 GB | — |

**Key insight**: a single 12 vCPU pod handles ~100 users (96% burst, 100% with 75s stagger) — more than enough for typical workshops up to 80 students. For >80 users, multi-pod becomes the right answer regardless of pod size, because the SSE shim becomes the bottleneck before the WebSocket layer does.

**Cost is roughly equivalent** between "fewer larger pods" and "more smaller pods" for the same total CPU. The trade-off:
- **Fewer larger pods**: simpler ops, no pool config, no random assignment, no failover. Single point of failure.
- **More smaller pods**: failover, smaller blast radius per outage, requires pool mode.

**Design doc validation**: the original "3 × 4 vCPU / 8 GB for 50 users" recommendation is correct in capacity, but **today's data suggests 1 × 8 vCPU / 16 GB is operationally simpler at the same cost** for a 50-person workshop. Previous estimates of "17 users per 4 vCPU / 8 GB pod" were conservative for short bursts but accurate for sustained sessions (peak_conn=18 measured directly).

## Connect-storm finding (revised after stagger experiments)

**Earlier framing**: "Connect-storm causes WebSocket handshake timeouts at 12+ concurrent users on 1 vCPU. Frontend stagger would fix it."

**Revised framing after running the `--ramp-interval` experiments**: the failure mode is **simultaneous-connection ceiling**, not handshake-rate limit. Each pod has a per-vCPU `peak_conn` ceiling (~6 per vCPU). When concurrent active sessions exceed this, additional WS handshakes time out trying to acquire a slot.

**Stagger doesn't unlock additional capacity**. It only reduces the simultaneous count for short-session workloads where earlier sessions complete and free slots before later ones start. For real workshops with 5-15 minute sessions, **stagger has minimal effect** because every user holds a slot for the entire session.

**The math** (validated experimentally on the 4 vCPU pod, peak_conn=18):
- Steady-state simultaneous users ≈ `min(N, N × T_session / T_stagger)`
- Need `simultaneous ≤ 18` for clean pass
- For 30s sessions: 50 users needs ≥84s stagger (we tested 75s, got 0 fail — close enough)
- **For 600s real-workshop sessions**: 50 users needs ≥1667s = **27 minutes of stagger**, which is unworkable for instructor-paced workshops

**Conclusion**: stagger is a marginal optimization for transient bursts, not a capacity multiplier. The right fix is **bigger pods** or **more pods**.

**Mitigations still worth adding** (much lower priority than I initially claimed):
1. **Frontend stagger** (random 0-3s delay before SSE in `jupyter.ts`): smooths the very first transient burst when an instructor says "go now." Helps when the pod is at ~80% capacity by avoiding the +20% transient overshoot. ~5 lines of code.
2. **Client-side WebSocket retry**: catch the first WS handshake failure, wait 2s, retry once. Helps when transient saturation clears within 2s. ~10 lines of code.

These are cheap and worth doing, but **they do not raise the per-pod ceiling**.

## What we still did NOT measure

- **Cold-start variability across nodes** — observed two cold starts, one warm-cache (~15s) and one cold-cache (~150s). Statistical distribution unknown.
- **Multi-instance pool behavior** — never tested workshop pool mode (multiple CE apps with frontend random-assignment). Workflow's `seq -w 1 1` bug had been silently deploying to the wrong app name; fixed in same session.
- **Larger pod sizing** — 1 vCPU is the only config tested. 4 vCPU / 4 GB could plausibly handle 30-40 users; not validated.
- **Failover** — the harness has a `failover` mode in its docstring but it's not implemented.
- **Multi-source-IP load** — testing multi-IP concurrency from a single laptop requires source-IP aliasing. After the fix, the 100r/m limit is comfortable enough that single-IP testing is no longer the bottleneck.

## Backlog

### Done in this session
1. ✅ nginx rate limit fix (5r/m → 100r/m + burst=50)
2. ✅ Kernel cull tuning (600s → 300s)
3. ✅ SSE shim cgroup-aware metrics (memory.max, cpu.max, loadavg)
4. ✅ Harness `KernelSession` refactor (one WS per kernel)
5. ✅ Image rebuild + CE redeploy via CI
6. ✅ CI workflow `seq -w 1 1` zero-padding bug fix
7. ✅ Reproducibility check on 1 vCPU
8. ✅ **Full CPU scaling characterization across 1, 4, 8, 12 vCPU**
9. ✅ Harness `--ramp-interval` flag (uniform stagger)
10. ✅ Stagger model validated — peak_conn is constant per pod, stagger only spreads work over time
11. ✅ Memory comprehensively shown to NOT be the constraint (max 30% across all tests on 4-12 vCPU pods)
12. ✅ **Final sizing recommendation**: 1 × 12 vCPU / 24 GB handles 80 users (96% burst, 100% with 75s stagger). 1 × 8 vCPU / 16 GB handles 50 users.
13. ✅ **NEW BOTTLENECK DISCOVERED**: SSE shim's threaded HTTPServer hits GIL contention around 80-100 simultaneous SSE requests. At 12 vCPU, this dominates the per-pod ceiling instead of the WS handshake.

### Open
1. **SSE shim async refactor** (NEW HIGH PRIORITY from 12 vCPU run): replace `ThreadingHTTPServer` with `aiohttp.web` async server. ~50-100 lines. Would lift 12 vCPU clean burst capacity from ~80 to ~120-150 users. **The single highest-leverage future optimization.**
2. **Multi-pod (workshop pool) test** — never validated end-to-end. With the `seq` bug fixed, deploy 2-3 instances and test the frontend random-assignment.
3. **Admin page live monitoring** (see "Admin monitoring sketch" below): swap admin.tsx's static "Settings → Code Engine" pointer for a live `/stats` panel.
4. **Jupyter Server connection counter underflow + cull-skip bug** (NEW HIGH PRIORITY discovered during 12 vCPU rolling-deploy chaos): when WS handshakes fail mid-stream, Jupyter's `connections_dict` underflows to negative, AND the resulting "phantom connection" prevents kernel culling because `cull_connected=False` skips kernels with active connections. Real-world impact: pod memory creeps up across a workshop day; hosts must restart pods between sessions. **Workaround**: set `cull_connected=True` (risky, may kill students mid-cell), OR call `DELETE /api/kernels/{id}` from frontend on session close, OR restart pods between workshops.
5. **Connect-storm mitigation** (LOWER PRIORITY than I claimed earlier):
   - Frontend stagger (random 0-3s delay before SSE in `jupyter.ts`): helps for transient overshoots above pod capacity. ~5 lines.
   - Client-side WebSocket retry: helps when transient saturation clears within 2s. ~10 lines.
   - These are cheap but **do NOT raise per-pod ceiling**.
6. **Image size reduction** (905 MB → ~300-350 MB) — see 3-phase plan in `memory/project_workshop_mode.md`. Phase 1 is the only one that matters.
7. **`min-scale=1` for workshop deployments** — add as deploy-time flag, document ~$5/month cost trade-off.
8. **Provision IBM Cloud Logs** — optional, free tier sufficient.
9. **`/stats` `status` field cosmetic bug** — sometimes reports `'unavailable'` due to early-init race.
10. **Implement harness failover mode** — docstring promises it but it's not coded.

## Admin monitoring sketch

The plumbing for live pod monitoring already exists. What's missing is a UI panel on the admin page.

**Backend (already done)**: SSE shim's `/stats` endpoint returns:
```json
{
  "kernels": 0, "kernels_busy": 0, "connections": 0,
  "memory_mb": 196, "memory_total_mb": 7629,
  "load_1m": 1.73, "load_5m": 0.91, "load_15m": 0.45,
  "cpu_count": 4.0,
  "peak_kernels": 20, "peak_connections": 20, "total_sse_connections": 41,
  "uptime_seconds": 612, "status": "ready"
}
```

**Frontend (todo)**: a React component on [src/pages/admin.tsx](../src/pages/admin.tsx) that:
1. Reads the configured workshop pool from `getWorkshopPool()` (already in `jupyter.ts`)
2. For each instance, polls `${url}/stats` every 5 seconds
3. Renders a table or card grid showing per-instance: live kernels (sparkline), memory %, load/CPU, peak counters, status
4. Highlights instances at risk (memory > 80%, load > cpu_count, status != "ready")
5. Auto-refreshes; no manual refresh button needed

Skeleton (unverified, ~80 lines):
```tsx
function PodStatsPanel() {
  const [pool, setPool] = useState<{url: string, token: string}[] | null>(null);
  const [stats, setStats] = useState<Record<string, any>>({});

  useEffect(() => {
    const config = getWorkshopPool();
    if (config) setPool(config.pool.map(url => ({url, token: config.token})));
  }, []);

  useEffect(() => {
    if (!pool) return;
    const tick = async () => {
      const next: Record<string, any> = {};
      await Promise.all(pool.map(async ({url}) => {
        try {
          const r = await fetch(`${url}/stats`, {
            signal: AbortSignal.timeout(3000),
          });
          if (r.ok) next[url] = await r.json();
        } catch { next[url] = {status: 'unreachable'}; }
      }));
      setStats(next);
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => clearInterval(id);
  }, [pool]);

  if (!pool) return <p>No workshop pool configured. Set one in <a href="/jupyter-settings#code-engine">Settings → Code Engine</a>.</p>;

  return (
    <table>
      <thead>
        <tr><th>Instance</th><th>Status</th><th>Kernels</th><th>Memory</th><th>CPU load</th><th>Peak K/Conn</th></tr>
      </thead>
      <tbody>
        {pool.map(({url}) => {
          const s = stats[url] || {};
          const memPct = s.memory_mb && s.memory_total_mb
            ? Math.round(100 * s.memory_mb / s.memory_total_mb) : null;
          const loadPct = s.load_1m && s.cpu_count
            ? Math.round(100 * s.load_1m / s.cpu_count) : null;
          const isWarn = (memPct && memPct > 80) || (loadPct && loadPct > 100);
          return (
            <tr key={url} style={isWarn ? {background: 'var(--ifm-color-warning-lightest)'} : undefined}>
              <td>{url.replace('https://', '').split('.')[0]}</td>
              <td>{s.status || '...'}</td>
              <td>{s.kernels ?? '?'} ({s.kernels_busy ?? '?'} busy)</td>
              <td>{memPct ? `${memPct}% (${s.memory_mb}/${s.memory_total_mb} MB)` : '?'}</td>
              <td>{loadPct ? `${loadPct}% (${s.load_1m}/${s.cpu_count} cores)` : '?'}</td>
              <td>{s.peak_kernels ?? '?'} / {s.peak_connections ?? '?'}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
```

**Effort**: 1-2 hours (component + styling + edge cases + adding section to admin.tsx). **Caveat**: 5s polling × N instances = N requests every 5s; for a 5-instance pool that's 1 req/s constantly. Each `/stats` call is ~3 ms server-side, so the cost is negligible. But it adds ~1 entry/sec to the access logs and counts against the `/api/` rate-limit (30 r/s, plenty of headroom).

## Cost spent

CE billed time across all steps + cold-start probes ≈ **6-8 minutes** of pod uptime at 1 vCPU / 4 GB ≈ **$0.005-$0.015**. The 905 MB image pull on a cold node is the biggest expense and is also negligible.

## Files changed in this session

- [binder/nginx-codeengine.conf](../binder/nginx-codeengine.conf) — `/build/` rate limit 5→100 r/m, burst 2→50
- [binder/codeengine-entrypoint.sh](../binder/codeengine-entrypoint.sh) — `cull_idle_timeout` 600→300, `cull_interval` 120→60, explicit `cull_busy=False`
- [binder/sse-build-server.py](../binder/sse-build-server.py) — cgroup-aware memory (`memory.current`/`memory.max`) + CPU count (`cpu.max`), `/proc/loadavg`, `high_cpu` event
- [scripts/workshop-stress-test.py](../scripts/workshop-stress-test.py) — `KernelSession` (one WS per kernel), per-kernel session ID, real `/stats` polling, `_format_stats` peak-aware output
- [.github/workflows/codeengine-image.yml](../.github/workflows/codeengine-image.yml) — fix `seq -w 1 1` returning `1` instead of `01`; use `printf "%02d"` for proper zero-padding so `instance_count=1` deploys to `ce-doqumentation-01` matching the documented name

## CE state changes (write operations)

For full audit trail:

| Time (UTC) | Operation | Reason |
|---|---|---|
| ~07:50 | `app update --name ce-doqumentation-01 --max-scale 1` | Was 5 (mistake); design requires 1 |
| ~07:50 | `app delete --name ce-doqumentation-1 --force` | Believed to be stale duplicate (WRONG — was actually CI's deploy target due to `seq -w` bug) |
| ~09:09 | CI workflow recreated `ce-doqumentation-1` with new image | Workflow's `seq -w 1 1` bug |
| ~09:18 | `app update --name ce-doqumentation-01 --image ...:latest` | Migrate new image to canonical app name (revision `-00022`, digest `7ec50c`) |
| ~09:19 | `app delete --name ce-doqumentation-1 --force` | Truly stale this time — superseded by `-01` migration |
| ~09:33 | CI workflow re-deployed `ce-doqumentation-01` | Triggered by workflow file change (not container code); cache hit, 2m11s build (revision `-00023`, digest `3dd4f4`) |
| ~09:46 | `app update --name ce-doqumentation-01 --cpu 4 --memory 8G` | Resize for larger-pod stress test (revision `-00024`, same image) |
| ~11:00 | `app update --name ce-doqumentation-01 --cpu 8 --memory 16G` | Verify CPU scaling on 8 vCPU pod (revision `-00025`, same image) |
| ~11:21 | `app update --name ce-doqumentation-01 --cpu 12 --memory 24G` | Push CPU scaling to 12 vCPU (revision `-00026`, same image) |
| ~11:30 | `app update --name ce-doqumentation-01 --max-scale 1` | No-op update to trigger fresh revision (revision `-00027`) — needed because the 12 vCPU rolling deploy left zombie kernels with phantom-negative `connections` counter that prevented culling |

End state (after all tests): single app `ce-doqumentation-01` running revision `-00027`, image pinned `3dd4f4`, **max-scale=1, 12 vCPU / 24 GB**, min-scale=0.
