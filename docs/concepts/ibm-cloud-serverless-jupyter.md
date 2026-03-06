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
│  (thebelab 0.4)  │ ────────────────────────────────▶ │  (user's account)    │
│                  │     WebSocket (kernel protocol)    │  Jupyter container   │
│                  │ ◀──────────────────────────────▶  │                      │
└─────────────────┘                                    └──────────────────────┘
        │                                                      │
        │  Settings page                                       │ scales 0→N
        │  ┌──────────────┐                                    │ per request
        └─▶│ CE endpoint  │                                    ▼
           │ CE API key   │                             ┌──────────────────────┐
           │ CE project   │                             │  Container Registry  │
           └──────────────┘                             │  (IBM CR / quay.io)  │
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

#### Setup Flow (Settings Page)

The existing Settings page (`src/pages/jupyter-settings.tsx`) gets a new
"IBM Cloud Code Engine" section, following the same UX pattern as the
IBM Quantum credentials section:

1. User enters their **Code Engine app URL** (e.g.,
   `https://my-jupyter.<region>.codeengine.appdomain.cloud`)
2. Optionally enters a **Jupyter token** for their deployment
3. doQumentation tests the connection (like the existing `testJupyterConnection`)
4. Credentials stored with TTL (same pattern as IBM Quantum credentials)

#### One-Click Deploy (Stretch Goal)

Provide a **"Deploy to Code Engine"** button/guide that:
- Links to IBM Cloud with a pre-configured Code Engine app template
- Uses our published container image from quay.io
- Pre-fills CPU (2 vCPU), memory (4 GB), scale-to-zero settings

### Integration with thebelab

thebelab 0.4 currently connects via Binder's SSE build-event protocol
(`ensureBinderSession` in `jupyter.ts:423`). The integration approach depends
on whether we keep the SSE protocol.

#### Option A: Binder-Compatible SSE Wrapper (Recommended)

Deploy a **thin SSE endpoint** alongside the Jupyter server in the Code Engine
container that mimics the Binder `/build/` protocol. This is the better choice
because:

- **Zero frontend changes** to `ExecutableCode/index.tsx` — the existing
  `ensureBinderSession()` → `getThebelabOptions()` → `doBootstrap()` flow
  works unchanged
- **Progress feedback preserved** — users see the same connecting → launching →
  ready phases during cold start (5–15s), which is important UX feedback
- **"Open in JupyterLab" works unchanged** — `openBinderLab()` uses the same
  SSE protocol and session reuse
- **Session reuse works unchanged** — `getBinderSession()`/`saveBinderSession()`
  with 8-min idle timeout works as-is
- **Minimal container change** — add a small Python endpoint to the Jupyter
  container (or a sidecar) that responds to `/build/` with SSE events

The SSE endpoint in the container would be ~30 lines of Python:

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

#### Option B: Direct Jupyter Server (Skip SSE)

Configure thebelab to connect directly via `serverSettings`, bypassing the
Binder SSE flow entirely.

**Pros:** No SSE wrapper needed in the container.
**Cons:** Requires changes to `ExecutableCode/index.tsx` bootstrap flow (~30
lines), loses progress feedback during cold start, "Open in JupyterLab" needs
a separate code path.

### Changes Required

| File | Change |
|------|--------|
| `src/config/jupyter.ts` | Add CE storage keys, detect CE config in `detectJupyterConfig()` |
| `src/pages/jupyter-settings.tsx` | Add "IBM Cloud Code Engine" section (URL + token input) |
| `binder/Dockerfile` | Add SSE `/build/` endpoint (small Python script or nginx location) |
| `.github/workflows/deploy.yml` | Add image build + push to quay.io/IBM CR |
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
| Workshop instructor | 100 hrs | **~$25.70** |

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

To reduce image size (and cold start):
1. Multi-stage build — install only runtime dependencies
2. Strip unused Qiskit extras — amd64-only packages, optional addons
3. Target ~1.5 GB image (down from ~3 GB)

## Security Considerations

- **User-owned accounts** — credentials never leave the user's browser
  (same as IBM Quantum token pattern: stored in localStorage with TTL)
- **CORS** — Code Engine apps support custom CORS headers; users configure
  their CE app to allow `*.doqumentation.org`
- **No persistent storage** — each container is ephemeral (matching Binder)
- **Token in localStorage** — same security model as existing IBM Quantum
  credentials, with configurable TTL (default 7 days)

## Implementation Plan

### Phase 1: Container + Settings UI
1. Add SSE `/build/` endpoint to `binder/Dockerfile`
2. Add Code Engine section to Settings page
3. Add `code-engine` environment to `jupyter.ts`
4. Publish image to quay.io via CI

### Phase 2: Documentation + Deploy Guide
1. Add setup guide: "Use your IBM Cloud account for interactive code"
2. Optional: IBM Cloud "Deploy to Code Engine" template
3. Add CE option to the onboarding/first-run experience

### Phase 3: Optimize
1. Reduce image size for faster cold starts
2. Add health-check / connection test in Settings
3. Consider shared/sponsored CE instance for anonymous users

## Open Questions

- [ ] Should we also offer a **project-sponsored** CE instance as default
      (for users without IBM Cloud accounts)?
- [ ] Image registry: quay.io (public, free) vs. IBM Container Registry
      (private, user's account)?
- [ ] Minimum image: can we make a "lite" image with just core Qiskit
      (~500 MB) for faster cold starts?
- [ ] Should the Settings page offer a guided IBM Cloud signup flow?
