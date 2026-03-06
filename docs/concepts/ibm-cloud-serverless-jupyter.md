# Concept: IBM Cloud Code Engine as Binder Alternative

## Problem

mybinder.org is used to provide remote Jupyter kernels for interactive code
execution on the GitHub Pages deployment. It suffers from:

- **Unreliable availability** — public mybinder instances go down frequently
- **Long cold-start times** — 30s to 5+ minutes when the image is not cached
- **No SLA** — free community service with no guarantees
- **Cache warming workaround** — we already run a GitHub Action (`binder.yml`)
  hitting 3 separate providers (2i2c, bids, gesis) to mitigate, but it's fragile

## Proposed Solution

Replace mybinder with **IBM Cloud Code Engine** — a fully managed serverless
container platform that can run our existing Jupyter kernel Docker image.
**Users bring their own IBM Cloud account** and configure it via the Settings
page, similar to how IBM Quantum credentials work today.

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
share it with their entire class. This enables:

- **One-time setup** — teacher deploys the container, shares the URL + token
- **Students just paste the URL** — no IBM Cloud account needed for students
- **Teacher controls the budget** — set max-instances and budget alerts
- **Workshop-friendly** — pre-warm with min-scale=1 before the session

#### Settings Page UX

The Settings page Code Engine section has two tabs:

**"Own Account" tab:**
1. Guided setup wizard (see below)
2. User enters their Code Engine app URL
3. Optionally enters a Jupyter token
4. Connection test + save

**"Classroom" tab:**
1. Student enters a **shared URL** provided by their teacher
2. Enters the **shared token** (teacher distributes this)
3. Connection test + save
4. Hint: "Ask your instructor for the Code Engine URL and token"

The teacher sees the same "Own Account" flow, but with additional guidance on
sharing: "Share this URL and token with your students so they can connect."

#### Teacher Deployment Guide

The Settings page includes a collapsible **"Setup Guide for Instructors"**:

1. Sign up / log in to [IBM Cloud](https://cloud.ibm.com)
2. Create a Code Engine project
3. Create an Application:
   - Image: `quay.io/janlahmann/doqumentation-jupyter:latest`
   - CPU: 2 vCPU, Memory: 4 GB
   - Min instances: 0 (or 1 for workshops)
   - Max instances: 10 (adjust for class size)
   - Port: 8888
4. Set environment variable: `JUPYTER_TOKEN=<your-chosen-token>`
5. Copy the app URL → share with students
6. (Optional) Set a budget alert under IBM Cloud → Billing

#### Max Instances Guidance for Teachers

| Class Size | Recommended Max Instances | Est. Cost/hr (all active) |
|-----------|--------------------------|--------------------------|
| 5–10      | 3                        | ~$0.90/hr                |
| 10–25     | 5                        | ~$1.50/hr                |
| 25–50     | 10                       | ~$3.00/hr                |

Code Engine routes multiple concurrent users to the same instance when
possible (each Jupyter server handles one kernel). For workshops, set
min-scale equal to expected concurrent users to eliminate cold starts.

### Guided Setup Flow (Settings Page)

The Settings page provides a **step-by-step wizard** for individual users:

#### Step 1: IBM Cloud Account
- "You need an IBM Cloud account. Most IBM Quantum users already have one."
- Link: **[Sign up for IBM Cloud](https://cloud.ibm.com/registration)**
  (opens in new tab)
- "Already have an account? Continue →"

#### Step 2: Create Code Engine App
- "Create a Code Engine application using our pre-built image."
- Option A: **Quick Deploy link** — pre-fills the IBM Cloud console with:
  - Image: `quay.io/janlahmann/doqumentation-jupyter:latest`
  - CPU: 2 vCPU, Memory: 4 GB, Port: 8888
  - Scale: min 0, max 3
- Option B: Manual steps (collapsible) with screenshots

#### Step 3: Configure Token
- "Set a Jupyter token for your deployment (environment variable)."
- Explains: `JUPYTER_TOKEN=<your-token>` in Code Engine app settings

#### Step 4: Connect
- Paste the Code Engine app URL
- Paste the Jupyter token
- **[Test Connection]** button (reuses existing `testJupyterConnection`)
- On success: "Connected! Code Engine is now your kernel provider."
- Credentials saved with TTL (same as IBM Quantum credentials, default 7 days)

### Integration with thebelab

thebelab 0.4 currently connects via Binder's SSE build-event protocol
(`ensureBinderSession` in `jupyter.ts:423`). We keep the SSE protocol via a
thin wrapper in the container.

#### Binder-Compatible SSE Wrapper

Deploy a **thin SSE endpoint** alongside the Jupyter server in the Code Engine
container that mimics the Binder `/build/` protocol:

- **Zero frontend changes** to `ExecutableCode/index.tsx` — the existing
  `ensureBinderSession()` → `getThebelabOptions()` → `doBootstrap()` flow
  works unchanged
- **Progress feedback preserved** — users see connecting → launching →
  ready phases during cold start (5–15s)
- **"Open in JupyterLab" works unchanged** — `openBinderLab()` uses the same
  SSE protocol and session reuse
- **Session reuse works unchanged** — `getBinderSession()`/`saveBinderSession()`
  with 8-min idle timeout works as-is

The SSE endpoint in the container (~30 lines of Python):

```python
# /build/ SSE endpoint — responds immediately since image is pre-built
async def build_sse(request):
    async def event_stream():
        yield sse_event({"phase": "connecting"})
        yield sse_event({"phase": "launching"})
        # Jupyter is already running in this container
        url = f"https://{request.host}/"
        token = os.environ.get("JUPYTER_TOKEN", "")
        yield sse_event({"phase": "ready", "url": url, "token": token})
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

The only frontend change: detect when the user has configured a Code Engine
endpoint and use that as the `binderUrl` instead of `mybinder.org`:

```typescript
// In detectJupyterConfig() — Code Engine configured by user
const ceUrl = getItem(STORAGE_KEY_CE_URL);
if (ceUrl) {
  return {
    enabled: true,
    baseUrl: ceUrl,
    wsUrl: ceUrl.replace(/^http/, 'ws'),
    token: getItem(STORAGE_KEY_CE_TOKEN) || '',
    thebeEnabled: true,
    labEnabled: true,  // user's own server — Lab access OK
    binderUrl: ceUrl,  // SSE endpoint lives at same origin
    environment: 'code-engine',
  };
}
```

### Changes Required

| File | Change |
|------|--------|
| `src/config/jupyter.ts` | Add CE storage keys, detect CE config in `detectJupyterConfig()` |
| `src/pages/jupyter-settings.tsx` | Add "Code Engine" section with Own Account / Classroom tabs, guided wizard |
| `binder/Dockerfile` | Add SSE `/build/` endpoint (small Python script) |
| `.github/workflows/deploy.yml` | Add image build + push to quay.io |
| `docusaurus.config.ts` | Add CE docs link (optional) |

**Not changed:** `ExecutableCode/index.tsx` — works as-is with SSE wrapper.

### Session Management

The existing session-reuse logic works unchanged:

- `ensureBinderSession()` checks `sessionStorage` for `dq-binder-session`
- If session exists and < 8 min old → reuse (no SSE call)
- If expired → new SSE call to Code Engine `/build/` → instant response
- `touchBinderSession()` on each cell execution extends the idle timer

The 8-min idle timeout in the frontend aligns with Code Engine's configurable
scale-down timeout (set to 600s / 10 min to provide buffer).

### Execution Priority Chain

**mybinder.org remains the default** — no change for users who don't configure
anything. IBM Cloud Code Engine is presented as the **(recommended) alternative**
in the Settings page for users who want faster, more reliable kernel access.

Priority order:

1. **Custom Jupyter server** — if configured (existing, unchanged)
2. **IBM Cloud Code Engine** — if configured (new, recommended)
3. **mybinder.org** — default for everyone else (existing, unchanged)
4. **Google Colab** — always available as escape hatch (existing, unchanged)

The Settings page promotes Code Engine with a "(Recommended)" badge and a
short explanation: faster startup, more reliable, free tier covers casual use.

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
| Casual learner | 5 hrs | **$0** (free tier) |
| Active student | 15 hrs | **~$0.30** (barely over free tier) |
| Power user / developer | 40 hrs | **~$7.75** |
| Workshop instructor (class of 25) | 50 hrs × 5 instances | **~$70** |

**Key insight:** Scale-to-zero means cost only accrues when running code. A
typical learner stays well within the free tier. A teacher running a 2-hour
workshop with 25 students pays ~$3.00 total.

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
- **CORS** — Code Engine apps support custom CORS headers; users configure
  their CE app to allow `*.doqumentation.org`
- **No persistent storage** — each container is ephemeral (matching Binder)
- **Token in localStorage** — same security model as existing IBM Quantum
  credentials, with configurable TTL (default 7 days)
- **Multi-user on shared instance** — each WebSocket connection gets its own
  Jupyter kernel; kernel isolation is handled by Jupyter's built-in
  multi-kernel architecture

## Container Image

Published to **quay.io** (public, free, no auth needed to pull):

- Registry: `quay.io/janlahmann/doqumentation-jupyter`
- Tags: `latest`, `<git-sha>`, `<date>`
- Built by: GitHub Actions on notebook/dependency changes
- Base: `quay.io/jupyter/base-notebook:python-3.12`
- Contents: full Qiskit stack from `binder/jupyter-requirements.txt`
- Addition: SSE `/build/` endpoint for Binder protocol compatibility

The same image works for:
- Individual users (own Code Engine account)
- Teachers (shared instance for classroom)
- Local Docker (`docker-compose.yml` — existing, unchanged)

## Implementation Plan

### Phase 1: Container + SSE Endpoint
1. Add SSE `/build/` endpoint to container (Python script + supervisor config)
2. Set up quay.io repository and CI image push in `deploy.yml`
3. Test: container starts, SSE responds, thebelab connects

### Phase 2: Settings UI + Guided Setup
1. Add `code-engine` environment to `jupyter.ts` (storage keys, detection)
2. Add Code Engine section to Settings page:
   - "Own Account" tab with guided wizard (4 steps)
   - "Classroom" tab with URL + token input
3. Connection test + credential persistence with TTL
4. Teacher setup guide (collapsible, in Settings page)

### Phase 3: Polish
1. Add max-instances guidance for teachers
2. Add CORS setup instructions to the guide
3. Add health-check endpoint for better connection testing
4. Quick Deploy link for IBM Cloud console (pre-filled template)
