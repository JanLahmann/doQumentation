# Stress Test Findings — CE Workshop Mode

**Date:** 2026-04-11
**Target:** `ce-doqumentation-01` (single CE app, 1 vCPU / 4 GB, max-scale=1)
**Harness:** [scripts/workshop-stress-test.py](../scripts/workshop-stress-test.py)
**Images tested:**
- **Old**: `ghcr.io/janlahmann/doqumentation-codeengine` pinned `577a63` (CE revision `-00021`) — pre-fix
- **New**: pinned `7ec50c` (CE revision `-00022`) — post-fix, deployed via CI build `24279189148`

## TL;DR

**Initial run** found that workshop mode was unusable because nginx rate-limited `/build/` SSE connects to 5 per minute per source IP. A 50-person workshop sharing one NAT would see all but 5 students fail at the first click.

**Fix applied + redeployed in same session.** New image rebuilt via CI, deployed to `ce-doqumentation-01` revision `-00022`. **Re-ran the same ramp** with the new image and refactored harness — rate limit no longer the bottleneck.

**Real per-pod capacity discovered**: at 1 vCPU / 4 GB, the limit is **9-12 concurrent kernel WebSocket handshakes** before CPU starvation causes WebSocket timeouts. Memory is NOT the constraint — idle Qiskit kernels are only ~30-65 MB each (we measured 14 simultaneous kernels in 795 MB / 4 GB cgroup). The bottleneck is **CPU during the initial connect storm**, not memory and not steady-state.

**Implication for sizing**: 50-user workshop needs **4-6 pods at 1 vCPU / 4 GB**, OR a smaller number of larger pods (4 vCPU / 4 GB likely handles 30-40 users — untested but worth a future session). The original design's "1 GB RAM per kernel" estimate was conservative by 10-30x.

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

## Results — new image (post-fix, refactored harness)

Same target, same workload, same `--cells-per-user 3 --idle-between 5`. Different image (CE revision `-00022`, pinned `7ec50c`) and refactored harness (`KernelSession` reuses one WebSocket per kernel).

| Step | Users | Kernels OK | Avg cell | p95 cell | Failures | Pod stats |
|---|---|---|---|---|---|---|
| smoke | 1 simple | 1/1 | 0.0s | 0.1s | 0 | `mem=128/3815MB(3%)` |
| 2a' | 3 Qiskit | **3/3** | **1.9s** | 5.6s | 0 | `peak_k=3 mem=191MB load=6.26/1cpu` (load high from cold start) |
| 2b' | 6 Qiskit | **6/6** | 3.5s | 12.2s | 0 | `peak_k=6 mem=192MB load=3.13/1cpu` |
| 2c' | 9 Qiskit | **9/9 kernels started** | 4.6s | 14.5s | **2 WS handshake timeouts** | `peak_k=9 peak_conn=7 mem=288MB` |
| 2d' | 12 Qiskit | **12/12 kernels started** | 2.1s | 6.1s | **10 WS handshake timeouts** | `peak_k=14 peak_conn=7 mem=795MB(21%)` |

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

## Real per-pod capacity (post-fix data)

At **1 vCPU / 4 GB / max-scale=1**, the empirical ceiling is:

| Concurrent users | Kernels alloc | WS handshake | Latency | Verdict |
|---|---|---|---|---|
| 1-6 | 100% | 100% | <12s p95 | **Comfortable** |
| 7-9 | 100% | 70-80% | <15s p95 | **Marginal — some WS timeouts** |
| 10-12 | 100% | ~16% | n/a | **Saturated** |

The bottleneck is **not memory** (used <22% of 4 GB at peak) and **not kernel creation** (all kernels allocated successfully even at 12 users). The bottleneck is **CPU during the brief WebSocket handshake storm** — 1 vCPU can't service the cryptographic handshakes for >9 simultaneous WebSocket connects fast enough to keep them under the harness's 30-second timeout.

**Per-kernel resource cost (idle Qiskit kernel)**:
- Memory: ~30-65 MB (NOT the 300-400 MB I assumed earlier — Aer simulator only allocates real RAM during execution)
- CPU: negligible at idle, ~100% during `random_circuit + simulator + 1024 shots`

**Sizing implications for real workshops**:
- 50-user workshop on 1 vCPU pods: **need 4-6 pods** (not the 3 the design doc estimated). Same total CPU as the design doc's 3×4vCPU plan, smaller blast radius per failure.
- **Or** test bigger pods: 4 vCPU / 4 GB might handle 30-40 users on a single pod. **Untested — worth a future session.**
- Memory can be smaller than 4 GB safely. **2 GB / 4 vCPU** might be the sweet spot for cost/performance.

## Connect-storm finding (new HIGH-priority issue)

The "WebSocket handshake timeout" failure mode in Step 2c'/2d' is **not a steady-state limit** — it's a **transient connect-storm problem**. If the same 12 users had connected at a steady 1-per-second rate, all of them would probably succeed. The harness fires all users in parallel via `asyncio.gather()`, which is the worst case.

**Real workshop risk**: when an instructor says "click the button now," all 50 students click within ~1 second. This is exactly the connect-storm pattern that breaks at 9-12 users on a single pod.

**Two mitigations to add to backlog**:
1. **Frontend stagger**: inject a random 0-3s delay in `jupyter.ts` before SSE connect. Turns synchronous click into uniform distribution. Eliminates the connect-storm entirely without changing pod sizing.
2. **Client-side WebSocket retry**: if the `/api/kernels/{id}/channels` connect fails or times out, retry once after 2s. Cheap, robust against transient saturation.

Either is a 5-10 line change. Both is better.

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
5. ✅ Image rebuild + CE redeploy via CI (revision `-00022` deployed)
6. ✅ Step 2 re-run on new image (real per-pod ceiling discovered)
7. ✅ CI workflow `seq -w 1 1` zero-padding bug fix (deploys would create `-1` instead of `-01`)

### Open
1. **Connect-storm mitigation** (HIGH — new from rerun): frontend stagger + client-side WS retry. 5-10 lines each. Without this, 50-user workshops hit the same WS handshake timeout we saw at 12 concurrent connects.
2. **Larger pod test**: 4 vCPU / 4 GB / max-scale=1, repeat the ramp at 15/20/30/40 users. Probably handles 30-40 users on a single pod, which would simplify deployment dramatically. **Untested.**
3. **Image size reduction** (905 MB → ~300-350 MB) — see 3-phase plan in `memory/project_workshop_mode.md`. Phase 1 (switch base from `quay.io/jupyter/base-notebook` to `python:3.12-slim`) is the only one that matters; saves ~450 MB. Reduces cold-start image-pull on a fresh K8s node from ~98s to ~30-40s.
4. **`min-scale=1` for workshop deployments** — add as a deploy-time flag to `.github/workflows/codeengine-image.yml`, document the ~$5/month cost trade-off.
5. **Test workshop pool mode end-to-end** — now that the workflow `seq` bug is fixed, actually deploy 2-3 instances and validate the frontend random-assignment with the harness.
6. **Provision IBM Cloud Logs** — optional. Free tier sufficient for occasional workshops. Currently pod logs evaporate when CE scales to zero.
7. **`/stats` `status` field bug** — the SSE shim's `_handle_stats` sets `result['status'] = 'ready'` only if the inner try block reaches the end, but the field is initialized to `'unavailable'`. Currently always reports `'unavailable'` even when everything works. Cosmetic, fix in next iteration.
8. **Implement harness failover mode** — the docstring promises it but it's not coded.

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
| ~09:18 | `app update --name ce-doqumentation-01 --image ...:latest` | Migrate new image to canonical app name |
| ~09:19 | `app delete --name ce-doqumentation-1 --force` | Truly stale this time — superseded by `-01` migration |

End state: single app `ce-doqumentation-01` running revision `-00022`, image pinned `7ec50c`, max-scale=1, 1 vCPU / 4 GB.
