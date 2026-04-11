# Stress Test Findings — CE Workshop Mode

**Date:** 2026-04-11
**Target:** `ce-doqumentation-01` (single CE app, 1 vCPU / 4 GB, max-scale=1)
**Harness:** [scripts/workshop-stress-test.py](../scripts/workshop-stress-test.py)
**Image revision tested:** `ghcr.io/janlahmann/doqumentation-codeengine` pinned `ff8a85` (CE revision `-00021`)

## TL;DR

Workshop mode is **not currently usable in production** because of a single nginx config line that rate-limits `/build/` SSE connects to 5 per minute per source IP. A 50-person workshop sharing one NAT (campus or conference WiFi) would see all but 5 students fail at the very first click. The fix is a one-line change to `binder/nginx-codeengine.conf` (already applied in this session, awaiting image rebuild + CE redeploy).

Beyond the rate limit, **we never reached the actual capacity ceiling** of the pod — every "failure" today was nginx rejecting connections, not the pod running out of CPU or memory. The real per-pod kernel capacity remains unknown until the rate limit fix lands and Step 2 is re-run.

We did discover several other issues worth fixing before any real workshop, listed below by severity.

## Test setup

- **Pre-test cleanup**: changed `ce-doqumentation-01` `max-scale` from `5` to `1` (the design doc requires `max-scale=1` because Jupyter kernels are stateful and CE has no session affinity); deleted a stale duplicate app `ce-doqumentation-1`.
- **Instrumentation** (option B, full): live `ibmcloud ce app logs --follow` streamed to file, `/api/status` polled every 1s, both running in background while harness ran. Files in `/tmp/dq-stress/`.
- **Workload**: 5-qubit `random_circuit(5, 3, measure=True)` + `AerSimulator().run(qc, shots=1024)` per cell — the harness's default `QISKIT_CELL`.
- **Conservative ramp**: started with 1-user smoke (`--simple` workload), then 1-user Qiskit, then `3 → 6 → 9` users. Did NOT push to higher counts because the failure mode was already clear at 6.

## Results

| Step | Users | Workload | Kernels OK | Avg cell | p95 cell | Failures | Notes |
|---|---|---|---|---|---|---|---|
| 0 | 1 | `print()` | 1/1 | 0.8s | 1.4s | 0 | Warm pod, end-to-end smoke |
| 1 | 1 | Qiskit | 1/1 | 1.2s | 3.0s | 0 | Pod cold-started during run |
| 2a | 3 | Qiskit | **3/3** | 3.4s | 9.5s | 0 | Same warm pod |
| 2b | 6 | Qiskit | **4/6** | 2.3s | 7.9s | 2 SSE | First failures |
| 2c | 9 | Qiskit | **4/9** | 2.2s | 7.6s | 5 SSE | >50% failure threshold tripped |

**The latency numbers in this table are inflated by ~200ms per cell** vs. real browser clients, because the original harness opened a new WebSocket per cell. The refactored harness (this session) uses one WebSocket per kernel and shows true per-cell latency. Pre-rebuild validation: `print('hello')` 0.8s → 0.0s. Treat the table as an upper bound.

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

## What we did NOT measure

- **Actual per-pod kernel capacity** — every "failure" today was nginx rate-limiting, not pod resource exhaustion. Once the nginx fix is deployed, Step 2 needs to be re-run to discover the real ceiling. Expected: 8-12 kernels on 1 vCPU / 4 GB before CPU contention dominates.
- **Cold-start variability across nodes** — only observed two cold starts, one warm-cache (~15s) and one cold-cache (~150s). Statistical distribution unknown.
- **Multi-instance pool behavior** — never tested workshop pool mode (multiple CE apps with frontend random-assignment).
- **Failover** — the harness has a `failover` mode in its docstring but it's not implemented.
- **Multi-source-IP load** — the per-IP rate limit cannot be tested from a single laptop. After the fix, it will still be present at 100r/m, so testing higher concurrency would need either (a) source IP rotation or (b) multiple test machines.

## Backlog

1. **Image rebuild + CE redeploy** — pending in this session. Container changes are on disk but not yet live.
2. **Re-run Step 2** after the new image is deployed, with the refactored harness, to discover real per-pod capacity.
3. **Image size reduction** (905 MB → ~400 MB) — strip unused Jupyter extensions, slim down Python deps. Reduces cold-start image-pull from ~98s to ~30-40s.
4. **`min-scale=1` for workshop deployments** — add as a deploy-time flag to `.github/workflows/codeengine-image.yml`, document the cost trade-off.
5. **Provision IBM Cloud Logs** for persistent log retention. Optional. Free tier sufficient for occasional workshops.
6. **Test workshop pool mode** — actually deploy 2-3 CE apps with `max-scale=1`, distribute users via the frontend's random-assignment logic, validate that the design works end-to-end.
7. **Implement harness failover mode** — the docstring promises it but it's not coded.
8. **Add `--source-ip-rotate` to harness** — bind to multiple local IPs to bypass per-IP rate limits during testing. Only useful if the host machine has multiple IPs.

## Cost spent

CE billed time across all steps + cold-start probes ≈ **6-8 minutes** of pod uptime at 1 vCPU / 4 GB ≈ **$0.005-$0.015**. The 905 MB image pull on a cold node is the biggest expense and is also negligible.

## Files changed in this session

- [binder/nginx-codeengine.conf](../binder/nginx-codeengine.conf) — `/build/` rate limit 5→100 r/m, burst 2→50
- [binder/codeengine-entrypoint.sh](../binder/codeengine-entrypoint.sh) — `cull_idle_timeout` 600→300, `cull_interval` 120→60, explicit `cull_busy=False`
- [binder/sse-build-server.py](../binder/sse-build-server.py) — cgroup-aware memory + CPU count, `/proc/loadavg`, `high_cpu` event
- [scripts/workshop-stress-test.py](../scripts/workshop-stress-test.py) — `KernelSession` (one WS per kernel), per-kernel session ID, real `/stats` polling, `_format_stats` peak-aware output
