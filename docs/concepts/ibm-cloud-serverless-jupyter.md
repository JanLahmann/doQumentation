# IBM Cloud Code Engine as Binder Alternative

## Status: Implemented

Core implementation complete across Phases 1–3. mybinder.org remains the
zero-config default; Code Engine is the recommended upgrade.

## Problem

mybinder.org is used to provide remote Jupyter kernels for interactive code
execution on the GitHub Pages deployment. It suffers from:

- **Unreliable availability** — public mybinder instances go down frequently
- **Long cold-start times** — 30s to 5+ minutes when the image is not cached
- **No SLA** — free community service with no guarantees
- **Cache warming workaround** — we already run a GitHub Action (`binder.yml`)
  hitting 3 separate providers (2i2c, bids, gesis) to mitigate, but it's fragile

## Solution

**IBM Cloud Code Engine** — a fully managed serverless container platform
running our Jupyter kernel Docker image. Users bring their own IBM Cloud
account and configure it via the Settings page, similar to how IBM Quantum
credentials work today.

The CE container includes the same notebooks branch content as mybinder,
so it is a **full drop-in replacement** — both in-page thebelab execution
and the "Open in JupyterLab" button work identically, just faster.

### Architecture

```
┌─────────────────┐                                    ┌──────────────────────┐
│  Browser         │     SSE (launch progress)         │  Code Engine App     │
│  (thebelab 0.4)  │ ────────────────────────────────▶ │  (user's own account │
│                  │     WebSocket (kernel protocol)    │   or teacher-shared) │
│                  │ ◀──────────────────────────────▶  │  Jupyter container   │
└─────────────────┘                                    └──────────────────────┘
        │                                                      │
        │  Settings page                                       │ scales 0→N
        │  ┌──────────────┐                                    │ per request
        └─▶│ CE endpoint  │                                    ▼
           │ Jupyter token│                             ┌──────────────────────┐
           └──────────────┘                             │  quay.io             │
                                                        │  (public image)      │
                                                        └──────────────────────┘
```

### Execution Priority Chain

mybinder.org remains the default — no change for users who don't configure
anything. Code Engine is the **(recommended)** alternative.

1. **Custom Jupyter server** — if configured (existing, unchanged)
2. **IBM Cloud Code Engine** — if configured (new, recommended)
3. **mybinder.org** — default for everyone else (existing, unchanged)
4. **Google Colab** — always available as escape hatch (existing, unchanged)

### User-Owned IBM Cloud Account Model

Each user deploys the Jupyter kernel to **their own** IBM Cloud Code Engine
project. This means:

- **No shared infrastructure cost** for the doQumentation project
- **Users control their own spending** and can set budget alerts
- **IBM Cloud free tier** covers ~14 hours/month at no cost
- **IBM Quantum users already have IBM Cloud accounts** — low friction
- **Isolation** — each user gets their own container, no cross-user concerns

### Teacher / Classroom Mode

A teacher or workshop instructor can deploy **one** Code Engine instance and
share it with their entire class:

- **One-time setup** — teacher deploys the container, shares the URL + token
- **Students just paste the URL** — no IBM Cloud account needed for students
- **Teacher controls the budget** — set max-instances and budget alerts
- **Workshop-friendly** — pre-warm with min-scale=1 before the session

## Implementation Details

### Container: `binder/Dockerfile.codeengine`

Single-port container (port 8080) managed by **supervisord** running three
services behind an **nginx** reverse proxy:

| Service | Internal Port | Description |
|---------|--------------|-------------|
| nginx | 8080 (exposed) | Reverse proxy, CORS, health check |
| Jupyter Server | 8888 | Kernel management, Lab UI, WebSocket |
| SSE Build Server | 9090 | Binder-compatible `/build/` endpoint |

**Base image:** `quay.io/jupyter/base-notebook:python-3.12`
**Contents:** Full Qiskit stack from `binder/jupyter-requirements.txt`

#### SSE Build Server (`binder/sse-build-server.py`)

Mimics the Binder `/build/` SSE protocol so `ensureBinderSession()` works
unchanged. Emits only 3 phases (vs 7+ for real Binder builds):

```python
phases = [
    {'phase': 'connecting'},              # 0.3s delay
    {'phase': 'launching'},               # 0.3s delay
    {'phase': 'ready', 'url': base_url, 'token': token},
]
```

URL determination: uses `CE_APP` env var if set, otherwise derives from
`Host` header + `X-Forwarded-Proto`.

CORS: `Access-Control-Allow-Origin: *` with OPTIONS preflight support.

#### Entrypoint (`binder/codeengine-entrypoint.sh`)

- Accepts `JUPYTER_TOKEN` env var or generates random 32-char hex
- Validates token (alphanumeric + dashes/underscores, min 8 chars)
- Writes `jupyter_server_config.py` at runtime with:
  - `c.ServerApp.token` from env
  - `c.ServerApp.allow_origin` from `CORS_ORIGIN` env (default: `https://janlahmann.github.io`)
  - `c.ServerApp.disable_check_xsrf = True` (thebelab 0.4.0 limitation)
  - `c.MappingKernelManager.cull_idle_timeout = 600` (10 min idle kernel cull)

#### nginx Reverse Proxy (`binder/nginx-codeengine.conf`)

All services exposed through single port 8080:

| Path | Backend | Notes |
|------|---------|-------|
| `/build/` | localhost:9090 | SSE, `proxy_buffering off` |
| `/api/` | localhost:8888 | WebSocket upgrade, 24h timeout |
| `/lab` | localhost:8888 | JupyterLab UI, WebSocket |
| `/terminals/` | localhost:8888 | Terminal WebSocket |
| `/health` | inline 200 | Returns `{"status":"ok"}` |
| `/` | localhost:8888 | Default catch-all |

Security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`.

### Frontend: `src/config/jupyter.ts`

#### Storage Keys

```typescript
STORAGE_KEY_CE_URL      = 'doqumentation_ce_url'
STORAGE_KEY_CE_TOKEN    = 'doqumentation_ce_token'
STORAGE_KEY_CE_SAVED_AT = 'doqumentation_ce_saved_at'
```

#### Detection (`detectJupyterConfig`)

CE is detected when `STORAGE_KEY_CE_URL` is set. Returns:

```typescript
{
  enabled: true,
  baseUrl: ceBase,                    // trailing slash stripped
  wsUrl: ceBase.replace(/^http(s?):\/\//, 'ws$1://'),
  token: getItem(STORAGE_KEY_CE_TOKEN) || '',
  thebeEnabled: true,
  labEnabled: false,                  // uses SSE flow, same as github-pages
  binderUrl: ceBase + '/v2/',         // .replace('/v2/', '/build/') → SSE endpoint
  environment: 'code-engine',
}
```

Key design decision: **`labEnabled: false`** — CE uses the same SSE session
flow as mybinder. The container includes the notebooks branch content, so
`openBinderLab()` opens JupyterLab with the actual notebook via
`${session.url}lab/tree/${nbPath}?token=${session.token}`.

#### Session Management

Existing session-reuse logic works unchanged:

- `ensureBinderSession()` checks `sessionStorage` for `dq-binder-session`
- If session exists and < 8 min old → reuse (no SSE call)
- If expired → new SSE call to CE `/build/` → near-instant response
- `touchBinderSession()` on each cell execution extends the idle timer

The 8-min idle timeout in the frontend aligns with CE's kernel cull timeout
(600s / 10 min) to provide buffer.

#### Environment-Aware Tab & Phase Hints

`openBinderLab()` adapts the loading tab for CE vs mybinder:

| | mybinder.org | Code Engine |
|---|---|---|
| Tab title | "Starting Binder..." | "Starting Code Engine..." |
| Initial text | "Connecting to mybinder.org..." | "Connecting to Code Engine..." |
| Phases shown | 7 (connecting → queue → fetch → build → push → launch → ready) | 3 (connecting → launching → ready) |
| Duration | 30s – 25 min | < 1s (warm) / 5–15s (cold) |
| Failure text | "Binder build failed..." | "Code Engine connection failed..." |

#### Credential TTL

CE credentials share the IBM Quantum TTL setting (1, 3, or 7 days).
`checkCEExpiry()` auto-clears expired credentials; `getCEDaysRemaining()`
returns days until expiry.

### Frontend: Settings Page (`src/pages/jupyter-settings.tsx`)

#### Code Engine Section

Heading: **"IBM Cloud Code Engine (Recommended)"**

Description: "Connect to your own serverless Jupyter kernel on IBM Cloud
Code Engine for instant startup and persistent sessions — no mybinder.org
queue. Recommended for the best experience. Without it, notebooks fall back
to mybinder.org (free, but slower)."

**Setup instructions** (collapsible `<details>` block):

1. Create a Code Engine project at IBM Cloud (Lite plan is free)
2. Create an Application with image `quay.io/janlahmann/doqumentation-jupyter:latest`
3. Set listening port to `8080` and add env var `JUPYTER_TOKEN`
4. Copy the Application URL and token below

**Form fields:**
- Application URL (`url` input, placeholder: `https://my-jupyter.us-south.codeengine.appdomain.cloud`)
- Jupyter Token (`password` input)

**Buttons:**
- **Save** — stores CE credentials with TTL
- **Test Connection** — fetches `{ceUrl}/health`, reports pass/fail
- **Clear** — removes CE credentials, shows "Falling back to mybinder.org"

**Environment banner** (top of settings page):
- github-pages: "Code execution uses Binder (may take a moment to start). For faster startup, configure Code Engine below."
- code-engine: "IBM Cloud Code Engine - Connected to {url}"

### Frontend: OpenInLabBanner

CE flows through the same `isBinder` path as github-pages — no special
casing needed. The key differences:

- **Tooltip**: "JupyterLab via Code Engine — fast serverless kernel" (vs "via Binder")
- **Raw Binder link**: hidden when CE is active (CE replaces it entirely)
- **Phase hints**: `CE_PHASE_HINTS` (connecting, launching) vs `BINDER_PHASE_HINTS` (7 phases)
- **Failed label**: generic "Failed" (not "Binder failed")

### Frontend: ExecutableCode

- **Run button title**: "Execute via Code Engine" (vs "via Binder" / "on local Jupyter server")
- **Clear Session button**: shown for both github-pages and code-engine
- **Binder hint** (pip install help): shown for both environments
- **Phase labels**: `usesBinder` flag covers both github-pages and code-engine
- **Thebelab bootstrap**: `getThebelabOptions()` handles CE alongside github-pages — reuses existing session via `serverSettings`

### CI: Image Build (`.github/workflows/codeengine-image.yml`)

- **Trigger**: push to `main` with changes in `binder/**`, or manual `workflow_dispatch`
- **Registry**: `quay.io/janlahmann/doqumentation-jupyter`
- **Tags**: `latest`, `<git-sha-short>`, `YYYYMMDD`
- **Dockerfile**: `binder/Dockerfile.codeengine`
- **Platform**: `linux/amd64`
- **Caching**: GitHub Actions layer cache

## Files Changed

| File | Change |
|------|--------|
| `src/config/jupyter.ts` | CE storage keys, `detectJupyterConfig()` CE branch, environment-aware `openBinderLab()` tab/hints, CE credential helpers with TTL |
| `src/pages/jupyter-settings.tsx` | CE section (Recommended), setup instructions, URL/token form, test/save/clear, environment banner with CE hint |
| `src/components/ExecutableCode/index.tsx` | CE button title, clear session for CE, binder hint for CE, `usesBinder` flag, `getThebelabOptions()` CE path |
| `src/components/OpenInLabBanner/index.tsx` | CE phase hints, CE tooltip, hide raw Binder link for CE |
| `binder/Dockerfile.codeengine` | New — CE container with nginx + supervisord + Jupyter + SSE |
| `binder/sse-build-server.py` | New — Binder-compatible SSE `/build/` endpoint |
| `binder/codeengine-entrypoint.sh` | New — token validation, Jupyter config generation |
| `binder/nginx-codeengine.conf` | New — single-port reverse proxy config |
| `.github/workflows/codeengine-image.yml` | New — CI image build + push to quay.io |

**Not changed:** `ensureBinderSession()` — works as-is with CE's SSE wrapper.

## Cost Estimate (User's IBM Cloud Account)

### Per-Instance Pricing (2 vCPU, 4 GB RAM)

| Resource | Rate | Per Hour | Per Month (730h) |
|----------|------|----------|-----------------|
| CPU | $0.00003431/vCPU-s | 2 × 3600 × $0.00003431 = **$0.247** | $180.30 |
| Memory | $0.00000356/GB-s | 4 × 3600 × $0.00000356 = **$0.051** | $37.40 |
| **Total per instance** | | **$0.298/hr** | **$217.70** |

### Free Tier (per IBM Cloud account, per month)

- 100,000 vCPU-seconds = **~13.9 hours** at 2 vCPU
- 200,000 GB-seconds = **~13.9 hours** at 4 GB RAM
- 100,000 HTTP requests

**The free tier covers ~14 hours of kernel time per month at no cost.**

### Realistic User Scenarios

| User Profile | Active hrs/month | Monthly Cost |
|-------------|-----------------|-------------|
| Casual learner | 5 hrs × 1 instance | **$0** (free tier) |
| Active student | 15 hrs × 1 instance | **~$0.30** (barely over free tier) |
| Power user / developer | 40 hrs × 1 instance | **~$7.75** |
| Workshop (class of 25, concurrency=1) | 2 hrs × 25 instances | **~$15.00** per session |
| Workshop (class of 25, concurrency=3) | 2 hrs × 9 instances | **~$10.80** per session |

**Key insight:** Scale-to-zero means cost only accrues when running code. A
typical learner stays well within the free tier.

### Comparison with Alternatives

| Service | Cost/hr (2vCPU/4GB) | Scale to Zero | Cold Start |
|---------|-------------------|---------------|------------|
| **IBM Code Engine** | **$0.30** | Yes | ~5-15s |
| mybinder.org | Free | N/A | 30s–5min |
| Google Cloud Run | ~$0.25 | Yes | 5-15s |
| AWS Lambda + EFS | ~$0.20 | Yes | 10-30s |
| Self-hosted (EC2/VM) | ~$0.10 | No (always on) | 0s |

## Cold Start Mitigation

Code Engine cold starts are 5–15 seconds (pulling a ~3 GB Qiskit image).
Users who want zero cold start can set min-scale=1 in their CE project
(~$0.30/hr / ~$217/month always-on). For most users, the 5–15s cold start
is acceptable — far better than Binder's 30s–5min.

**For teachers/workshops:** Set min-scale to expected concurrent users 15
minutes before the session starts. Reset to 0 after. This keeps cost to the
actual workshop duration.

## Security Considerations

- **User-owned accounts** — credentials never leave the user's browser
  (same as IBM Quantum token pattern: stored in localStorage with TTL)
- **Classroom mode** — teacher distributes a read/execute-only token; students
  cannot modify the Code Engine deployment or access the teacher's IBM Cloud
  console
- **CORS** — configurable via `CORS_ORIGIN` env var (default: `https://janlahmann.github.io`);
  nginx adds `Access-Control-Allow-Origin` headers; SSE endpoint allows `*`
- **XSRF disabled** — thebelab 0.4.0 cannot send XSRF tokens; security is via
  token authentication only
- **No persistent storage** — each container is ephemeral (matching Binder)
- **Token in localStorage** — same security model as existing IBM Quantum
  credentials, with configurable TTL (1, 3, or 7 days)
- **Kernel isolation** — each WebSocket connection gets its own Jupyter kernel;
  idle kernels are culled after 10 minutes (600s)

## Container Image

Published to **quay.io** (public, free, no auth needed to pull):

- Registry: `quay.io/janlahmann/doqumentation-jupyter`
- Tags: `latest`, `<git-sha>`, `YYYYMMDD`
- Built by: GitHub Actions on `binder/**` changes (`.github/workflows/codeengine-image.yml`)
- Base: `quay.io/jupyter/base-notebook:python-3.12`
- Contents: full Qiskit stack from `binder/jupyter-requirements.txt` + notebooks branch
- Services: nginx (8080) + Jupyter Server (8888) + SSE Build Server (9090)

The same image works for:
- Individual users (own Code Engine account)
- Teachers (shared instance for classroom)
- Local Docker (`docker-compose.yml` — existing, unchanged)

## Scaling Model

Each Jupyter kernel holds user state (variables, imports, circuit objects) —
**users cannot share a kernel**. Code Engine's `--concurrency` setting controls
how many users are routed to one container instance:

- **`concurrency=1` (recommended):** Each user gets their own dedicated
  container (2 vCPU, 4 GB). Full isolation, matches Binder's model exactly.
  Scaling = more identical instances.
- **`concurrency=2–3` (cost-saving option):** Multiple Jupyter kernels run in
  one container. Jupyter natively supports multiple independent kernels per
  server. Requires a larger instance (4 vCPU, 8 GB) so each kernel gets
  sufficient memory for Qiskit workloads (~2 GB per kernel).

**Why not one big instance?** A single Qiskit kernel doesn't benefit from
more than ~2 vCPU (quantum circuit simulation is memory-bound, not CPU-bound
at the sizes used in tutorials). Scaling up a single instance to 8 vCPU / 16 GB
would serve ~4 users but costs the same as 4 separate 2 vCPU / 4 GB instances
— no savings, and a crash takes down all users instead of one.

### Max Instances Guidance for Teachers

**Option 1: `concurrency=1`, 2 vCPU / 4 GB per instance (recommended)**

| Class Size | Max Instances | Est. Cost/hr (all active) |
|-----------|--------------|--------------------------|
| 5–10      | 10           | ~$3.00/hr                |
| 10–25     | 25           | ~$7.50/hr                |
| 25–50     | 50           | ~$15.00/hr               |

**Option 2: `concurrency=3`, 4 vCPU / 8 GB per instance (budget-friendly)**

| Class Size | Max Instances | Est. Cost/hr (all active) |
|-----------|--------------|--------------------------|
| 5–10      | 4            | ~$2.40/hr                |
| 10–25     | 9            | ~$5.40/hr                |
| 25–50     | 17           | ~$10.20/hr               |

## Future Work

- **Classroom tab** — dedicated "Classroom" tab in Settings (student pastes
  teacher-shared URL + token) alongside "Own Account" tab
- **Guided setup wizard** — step-by-step 4-step wizard replacing the current
  collapsible instructions
- **Quick Deploy link** — pre-filled IBM Cloud console URL for one-click
  application creation
- **CORS setup instructions** — guide users through configuring `CORS_ORIGIN`
  for custom domains
