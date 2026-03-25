# Workshop Mode: Multi-Instance Code Engine

## Context

For workshops/classes with ~50 participants, a single CE instance can't handle the load (each Qiskit kernel uses ~200-400 MB RAM; CE max is 24 GB). Horizontal scaling (`max-scale > 1`) doesn't work because Jupyter kernels are stateful — CE's load balancer would route requests to different instances, breaking sessions.

**Solution**: Deploy N identical CE apps (each `max-scale=1`), each independent. Fewer larger instances are better than many small ones — fewer cold starts, more CPU headroom per kernel, simpler management. Default: **3 apps x 4 vCPU / 8 GB** (~17 users each, comfortable headroom). Configurable at deploy time.

Frontend distributes users randomly across the pool and sticks to the assigned instance for the session. The organizer shares a single URL containing the pool config.

**Sizing rationale**: Each Qiskit kernel uses ~300-400 MB RAM + bursty CPU (Aer simulator). For 50 users at 400 MB each = ~20 GB total. CE max per instance: 12 vCPU / 24 GB. Options:
- 2 x 8 vCPU / 16 GB — simplest, but tight if everyone runs simulators simultaneously
- **3 x 4 vCPU / 8 GB** — good balance (recommended default)
- 5 x 2 vCPU / 4 GB — more failover but more cold starts and management overhead

## Files to modify

### 1. `src/config/jupyter.ts` — Workshop pool logic

**New storage keys:**
- `doqumentation_workshop_pool` (localStorage) — JSON: `{pool: string[], token: string, version: number}`
- `dq-workshop-assigned` (sessionStorage) — assigned instance URL for this tab
- `dq-workshop-pool-version` (sessionStorage) — pool version at time of assignment

**New functions (~50 lines):**
- `saveWorkshopPool(pool: string[], token: string)` — validates URLs (must be https), saves to localStorage
- `getWorkshopPool(): {pool: string[], token: string} | null` — reads + parses
- `clearWorkshopPool()` — removes pool + clears sessionStorage assignment
- `assignWorkshopInstance(): string` — returns existing assignment from sessionStorage, or picks random URL from pool and saves it. If assigned URL is no longer in pool, re-assigns. Also re-assigns if pool version has changed (organizer updated the pool mid-workshop) — but only for **unassigned or new** tabs; tabs with an active kernel keep their assignment to avoid losing state.
- `getWorkshopInstanceStats(pool, token): Promise<{url: string, kernels: number}[]>` — queries `/api/kernels?token=TOKEN` on each instance, returns kernel count per instance. Used by organizer dashboard and load-aware assignment.

**Modify `buildConfigFor('code-engine')` (line ~173):**
- Check `getWorkshopPool()` first. If active, use `assignWorkshopInstance()` for baseUrl/wsUrl/binderUrl.
- Fall through to existing single-CE logic if no workshop pool.

**Modify `getAvailableBackends()` (line ~103):**
- If workshop pool is active, show detail as `"Workshop (N instances)"` instead of single CE URL.

**Add workshop key to `ALL_JUPYTER_KEYS` (line ~56).**

**Add failover to `ensureBinderSession()` (~line 661):**
- On SSE connection error, if workshop pool is active: try next instance in pool (round-robin), update sessionStorage, retry. Max `pool.length` attempts before giving up.

**Load-aware assignment (optional, improves distribution):**
- `assignWorkshopInstance()` can optionally call `getWorkshopInstanceStats()` to pick the least-loaded instance instead of pure random. This is async, so fallback to random if the stats call times out (2s).
- Pure random is the default (no network call needed). Load-aware is used when the organizer enables it or when the pool has >3 instances.

### 2. `src/pages/jupyter-settings.tsx` — Workshop UI

**New state variables (after line ~187):**
```typescript
const [workshopPool, setWorkshopPoolState] = useState<{pool: string[], token: string} | null>(null);
const [workshopAssigned, setWorkshopAssigned] = useState<string | null>(null);
```

**URL fragment auto-import — extend the existing `useEffect` at line 251:**
- Before the existing hash-to-details logic, check for `#workshop=BASE64`:
  ```
  if (hash.startsWith('workshop=')) {
    const config = JSON.parse(atob(hash.slice('workshop='.length)));
    saveWorkshopPool(config.pool, config.token);
    window.history.replaceState(null, '', window.location.pathname + '#code-engine');
    // update local state, refresh backends
  }
  ```
- This lets the organizer share: `https://doqumentation.org/jupyter-settings#workshop=eyJwb29s...`

**Modify the CE `<details>` section (lines 931-1020):**
- If workshop pool is active, show a workshop status panel instead of the single URL/token inputs:
  - "Workshop Mode: N instances" badge
  - Which instance is assigned to this tab
  - "Leave Workshop" button (calls `clearWorkshopPool()`)
- If no workshop pool, show existing CE form unchanged
- Add a "Join Workshop" subsection below the form: textarea/input for base64 config string + "Join" button (manual alternative to URL fragment)

**Organizer dashboard (within workshop panel):**
- "Instance Status" section with a "Refresh" button
- Calls `getWorkshopInstanceStats()` → displays table:
  ```
  Instance 1  ce-doqumentation-01...cloud  12 kernels  ● Online
  Instance 2  ce-doqumentation-02...cloud   8 kernels  ● Online
  Instance 3  ce-doqumentation-03...cloud   0 kernels  ○ Scaling up...
  ```
- Each row: instance URL (truncated), active kernel count, status (online/offline/starting)
- Status is determined by the fetch result: 200 = online, 502/503 = scaling up, timeout = offline
- "Update Pool" button: lets organizer add/remove instance URLs mid-workshop → bumps pool version → saves to localStorage → cross-tab sync via `storage` event

### 3. `.github/workflows/codeengine-image.yml` — Multi-app deploy

**Add `workflow_dispatch` inputs:**
```yaml
on:
  workflow_dispatch:
    inputs:
      instance_count:
        description: 'Number of CE instances (1-10)'
        default: '1'
        type: choice
        options: ['1', '2', '3', '5', '10']
      cpu:
        description: 'vCPUs per instance'
        default: '4'
        type: choice
        options: ['1', '2', '4', '8', '12']
      memory:
        description: 'Memory per instance'
        default: '8G'
        type: choice
        options: ['2G', '4G', '8G', '16G', '24G']
```

**Replace single deploy step with matrix job:**
- Generate instance list from input (or default to just `[1]` for push triggers)
- Each matrix entry creates/updates app `ce-doqumentation-{NN}` within the same CE project
- All apps share: same image, same `JUPYTER_TOKEN` secret, same CORS_ORIGIN
- `--min-scale 0 --max-scale 1 --cpu 4 --memory 8G` (default; configurable via workflow inputs)
- Use `ibmcloud ce app get` to check existence; `create` if new, `update` if exists

**Add output step:**
- After all deploys, list all `ce-doqumentation-*` app URLs
- Generate base64 workshop config JSON
- Print the shareable URL: `https://doqumentation.org/jupyter-settings#workshop=BASE64`

### 4. `scripts/ibmcloud-spending-limit.sh` — Multi-app awareness

**Replace single-app check (lines 75-93) with loop:**
- `ibmcloud ce app list` → filter `ce-doqumentation-*`
- Verify `max-scale=1` for each
- Summary: "N apps x max-scale=1, estimated $0-N*1.50/month"

### 5. Dynamic scaling mid-workshop

**How it works**: The organizer deploys additional CE apps (via workflow or CLI) and adds their URLs to the pool using the "Update Pool" button on the settings page. This bumps the pool `version` in localStorage.

**Client behavior on pool update:**
- `localStorage` `storage` event fires in all tabs on the same origin
- Tabs that **don't yet have a kernel** (haven't connected): `assignWorkshopInstance()` detects version mismatch → re-assigns to least-loaded instance
- Tabs that **have an active kernel**: keep their current assignment (kernel state preserved). They only re-assign on failover (instance down) or manual page refresh.
- New tabs opened after the update: assigned via load-aware logic across the expanded pool

**Scaling down**: Organizer removes a URL from the pool. Users assigned to the removed instance continue working until their kernel idles out or they refresh. On next connection attempt, failover kicks in → re-assigned to a remaining instance. Kernel state is lost but this is expected when scaling down.

**No server-side coordination needed** — all assignment logic is client-side. The SSE server on each instance is stateless and independent.

### 6. `binder/sse-build-server.py` — Add `/stats` endpoint

Add a lightweight `/stats` GET endpoint (no auth required, like `/health`):
```python
def do_GET(self):
    if self.path == '/stats':
        # Query local Jupyter for kernel count
        token = os.environ.get('JUPYTER_TOKEN', '')
        kernels = json.loads(urllib.request.urlopen(
            f'http://127.0.0.1:{JUPYTER_PORT}/api/kernels?token={token}', timeout=3
        ).read())
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', CORS_ORIGIN)
        self.end_headers()
        self.wfile.write(json.dumps({
            'kernels': len(kernels),
            'status': 'ready'
        }).encode())
        return
```

Expose via nginx at `/stats` (add to `nginx-codeengine.conf`, rate-limited like `/health`).

Frontend `getWorkshopInstanceStats()` calls `/stats` on each pool URL instead of `/api/kernels` directly — simpler, CORS-safe, no token in the browser request to the stats endpoint.

## Files NOT modified

- `binder/codeengine-entrypoint.sh` — identical across instances
- `src/components/ExecutableCode/index.tsx` — calls `detectJupyterConfig()` transparently
- `src/components/OpenInLabBanner/index.tsx` — calls `ensureBinderSession()` transparently
- `Dockerfile.jupyter` — same image for all instances

## Workshop organizer workflow

1. Go to Actions > "Code Engine Image" > Run workflow > set instance_count=3, cpu=4, memory=8G
2. Workflow deploys 3 apps (4 vCPU / 8 GB each), outputs shareable workshop URL
3. Share URL with participants (slide, QR code, email)
4. Participants click link → auto-configured → randomly distributed
5. After workshop: instances scale to zero automatically ($0 ongoing)

## Stress test: `scripts/workshop-stress-test.py`

New Python script (~150 lines) that simulates N concurrent users against a single CE instance to find its capacity limits. Uses `asyncio` + `aiohttp` + `websockets`.

**What each simulated user does:**
1. GET `/build/` (SSE) → parse `ready` event → extract token
2. POST `/api/kernels` with `Authorization: token TOKEN` → get kernel ID
3. WebSocket to `/api/kernels/{id}/channels` → send `execute_request` with a representative Qiskit workload:
   ```python
   from qiskit.circuit.random import random_circuit
   from qiskit_aer import AerSimulator
   qc = random_circuit(5, 3, measure=True)
   result = AerSimulator().run(qc, shots=1024).result()
   print(result.get_counts())
   ```
4. Wait for `execute_reply` → record latency
5. Idle for configurable interval (simulates reading time), then execute another cell
6. After N cells, shut down kernel (`DELETE /api/kernels/{id}`)

**Two modes:**

### Single-instance mode (capacity testing)
Find the breaking point of one instance size.
```bash
python scripts/workshop-stress-test.py \
  --url https://ce-doqumentation-01...cloud \
  --token YOUR_TOKEN \
  --users 5,10,15,20,25,30 \
  --cells-per-user 3 \
  --idle-between 10
```
Output:
```
Users: 10  |  Kernels: 10/10  |  Avg latency: 4.2s  |  Memory: 3.8/8.0 GB  |  Failures: 0
Users: 20  |  Kernels: 20/20  |  Avg latency: 8.1s  |  Memory: 7.2/8.0 GB  |  Failures: 0
Users: 25  |  Kernels: 23/25  |  Avg latency: 15.3s |  Memory: 8.0/8.0 GB  |  Failures: 2 (OOM)
=> Capacity: ~20 users on 4 vCPU / 8 GB
```

### Workshop mode (end-to-end rehearsal)
Simulates the full participant experience across the pool — same as a real class.
```bash
# Test with workshop config (same base64 the participants would use)
python scripts/workshop-stress-test.py \
  --workshop eyJwb29sIjpbImh0dHBzOi8vY2UtMDEuLi4iLCJodHRwczovL2NlLTAyLi4uIl0sInRva2VuIjoiYWJjMTIzIn0= \
  --users 50 \
  --cells-per-user 5 \
  --idle-between 15

# Or pass URLs directly
python scripts/workshop-stress-test.py \
  --pool https://ce-01...,https://ce-02...,https://ce-03... \
  --token YOUR_TOKEN \
  --users 50 \
  --cells-per-user 5
```
Each simulated user:
1. Randomly picks an instance (same algorithm as the frontend: random, or load-aware if `--load-aware`)
2. Connects via SSE `/build/` → gets token
3. Starts kernel, executes cells, idles between cells
4. Sticks to assigned instance for the entire session (same as real users)

Output:
```
Workshop test: 50 users across 3 instances
  Instance 1 (ce-01): 18 users | Avg latency: 5.1s | p95: 9.2s | Memory: 6.8/8.0 GB | Failures: 0
  Instance 2 (ce-02): 17 users | Avg latency: 4.8s | p95: 8.7s | Memory: 6.5/8.0 GB | Failures: 0
  Instance 3 (ce-03): 15 users | Avg latency: 4.5s | p95: 8.1s | Memory: 5.9/8.0 GB | Failures: 0
  Total: 50/50 users connected | 0 failures | Distribution: balanced
  Recommendation: OK — all instances under 85% memory, p95 latency < 10s
```

### Failover test (optional flag)
```bash
# Kill one instance mid-test, verify users reconnect
python scripts/workshop-stress-test.py --pool ... --users 30 --test-failover
```
After 50% of cells complete, simulates one instance going down (stops sending to it). Verifies that affected users reconnect to another instance and resume.

**Metrics collected (both modes):**
- Kernel startup time (POST latency)
- Cell execution latency (per user, average, p95)
- Per-instance kernel count + memory from `/stats`
- Failure count (connection refused, OOM kills, timeouts)
- User distribution across instances
- The "breaking point" — user count where failures start or latency exceeds threshold (default 30s)

**Ramp mode:** Incrementally adds users (from `--users` list), runs the workload at each level, reports metrics, stops if failure rate > 50%. This tells you: "this instance handles ~20 users comfortably, degrades at 25, fails at 30."

**Dependencies:** `pip install aiohttp websockets` (not added to project deps — standalone test script)

**Enhancement to `/stats` endpoint:** Add memory info to the response:
```python
import resource
# or read /proc/meminfo on Linux
'memory_mb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
```
Actually, better: read from Jupyter's `/api/status` which already returns `memory` usage.

## Instructor guide: `docs/workshop-setup.mdx`

New documentation page for workshop organizers. Linked from the Settings page CE section ("Running a workshop? See the Workshop Setup Guide"). Added to the navbar under a "Workshop" item or as a link in the CE setup instructions.

### Contents

**1. Prerequisites**
- IBM Cloud account with Code Engine access (free tier works for small workshops)
- GitHub repo access (to trigger deploy workflow)
- Estimated cost table:

| Workshop size | Instances | Size each | Est. cost (3h) |
|--------------|-----------|-----------|----------------|
| 10-15 users | 1 | 4 vCPU / 8 GB | Free tier |
| 20-30 users | 2 | 4 vCPU / 8 GB | ~$1-2 |
| 40-50 users | 3 | 4 vCPU / 8 GB | ~$2-3 |

**2. Before the workshop (day before)**
- Step-by-step: Go to Actions > "Code Engine Image" > Run workflow
  - Set `instance_count`, `cpu`, `memory` based on class size
  - Screenshot of the workflow dispatch UI
- Wait for workflow to complete (~5 min)
- Copy the workshop URL from the workflow output
- Run stress test to verify capacity:
  ```bash
  pip install aiohttp websockets
  python scripts/workshop-stress-test.py --pool URL1,URL2,URL3 --token TOKEN --users 10 --cells-per-user 2
  ```
- Warm up instances: visit each CE URL once (or run a quick test) so they're not cold-starting during class

**3. Share with participants**
- Options: QR code, URL in slides, paste in chat
- The URL auto-configures everything — participants just click and start coding
- No IBM Cloud account needed for participants

**4. During the workshop**
- Monitor via Settings page > Code Engine > Instance Status dashboard
- Watch for: memory > 80%, latency spikes, offline instances
- If an instance is struggling:
  - Deploy additional instances (re-run workflow with higher `instance_count`)
  - Add new URLs via "Update Pool" button
  - New connections automatically distributed to new instances
- If an instance goes down: affected users auto-reconnect to another instance (kernel state lost, but code cells are still in the page)

**5. After the workshop**
- Instances scale to zero automatically after 10 min idle — no action needed
- To delete instances entirely: `ibmcloud ce app delete --name ce-doqumentation-02` (etc.)
- Run spending check: `bash scripts/ibmcloud-spending-limit.sh`

**6. Troubleshooting**
- "Instance won't start" → Check CE project quotas, verify image exists in ghcr.io
- "Users can't connect" → Verify CORS_ORIGIN matches your domain, check JUPYTER_TOKEN matches
- "Slow execution" → Too many users per instance, scale up (add instances or increase memory)
- "Kernel dies" → OOM — increase memory per instance or add more instances to spread load
- "Cold start takes 60s+" → Pre-warm instances before class starts

**7. Quick reference card** (one page, printable)
- Deploy command, workshop URL format, monitoring URL, emergency scale-up steps

## Verification

1. **Unit**: Test `assignWorkshopInstance()` picks randomly, sticks on re-call, failover rotates, re-assigns on pool version change
2. **Manual — single instance**: Save workshop pool with 1 URL via settings page, verify thebelab + JupyterLab work as before
3. **Manual — URL import**: Visit `jupyter-settings#workshop=BASE64`, verify auto-import, CE section shows workshop mode
4. **Manual — multi-instance**: Deploy 2 CE apps, generate workshop URL, open in multiple browser tabs, verify they get distributed across instances
5. **Manual — dashboard**: Open settings page with workshop active, click "Refresh" on instance status, verify kernel counts shown per instance
6. **Manual — live scaling**: Add a new instance URL via "Update Pool", open a new tab, verify it can be assigned to the new instance. Verify existing tabs keep their assignment.
7. **Manual — failover**: Stop one CE app, verify assigned tab falls back to another instance on next connection
8. **Manual — `/stats` endpoint**: `curl https://ce-instance/stats` returns `{"kernels": N, "status": "ready"}`
9. **CI**: Workflow runs with `instance_count=2`, verify both apps created and workshop URL printed
10. **Stress test — single**: Run `workshop-stress-test.py --url ... --users 5,10,15,20,25,30` against one instance, determine capacity per instance size
11. **Stress test — workshop**: Run `workshop-stress-test.py --pool ... --users 50 --cells-per-user 5` against the full pool, verify balanced distribution, acceptable latency, no failures
12. **Stress test — failover**: Run with `--test-failover`, verify users reconnect after simulated instance failure