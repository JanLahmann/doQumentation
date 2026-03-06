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

### Architecture

```
┌─────────────────┐     HTTPS (SSE build events)      ┌──────────────────────┐
│  Browser         │ ──────────────────────────────────▶│  Code Engine App     │
│  (thebelab 0.4)  │     WebSocket (kernel protocol)   │  (Jupyter container) │
│                  │ ◀────────────────────────────────▶│                      │
└─────────────────┘                                    └──────────────────────┘
                                                              │
                                                              │ scales 0→N
                                                              │ per request
                                                              ▼
                                                       ┌──────────────────────┐
                                                       │  Container Registry  │
                                                       │  (IBM CR / quay.io)  │
                                                       └──────────────────────┘
```

### How It Works

1. **Container image** — Reuse the existing `binder/Dockerfile` (based on
   `quay.io/jupyter/base-notebook:python-3.12` + `jupyter-requirements.txt`).
   Push the built image to IBM Container Registry or quay.io.

2. **Code Engine App** — Deploy as a Code Engine "Application" (HTTP-triggered,
   auto-scaling). Configure:
   - Min instances: **0** (scale to zero when idle → no cost)
   - Max instances: **10** (cap concurrent users)
   - CPU: **2 vCPU**, Memory: **4 GB** (sufficient for Qiskit workloads)
   - Timeout: **600s** (10 min idle before scale-down)
   - Port: **8888** (Jupyter default)

3. **Binder-compatible API shim** — Two integration paths (see below).

4. **CI/CD** — GitHub Actions builds & pushes the image on notebook changes
   (replaces the current `notebooks` branch + Binder cache warming).

### Integration with thebelab

thebelab 0.4 currently connects via Binder's build-event SSE protocol. There
are two integration approaches:

#### Option A: Direct Jupyter Server (Recommended)

Skip the Binder protocol entirely. Code Engine provides a stable URL that
already has the kernel ready (no build step needed). Configure thebelab to
connect directly:

```typescript
// In src/config/jupyter.ts — new environment case
if (hostname.endsWith('doqumentation.org')) {
  return {
    enabled: true,
    baseUrl: 'https://doqumentation-kernel.<region>.codeengine.appdomain.cloud',
    wsUrl:  'wss://doqumentation-kernel.<region>.codeengine.appdomain.cloud',
    token: '<rotated-token>',
    thebeEnabled: true,
    labEnabled: false,
    environment: 'github-pages',  // or new 'code-engine' environment
  };
}
```

In `ExecutableCode/index.tsx`, when `baseUrl` is already set (non-empty), bypass
the Binder SSE launch flow and bootstrap thebelab directly with the server URL.
thebelab 0.4 supports this — its `bootstrap()` accepts `serverSettings` with
`baseUrl` and `token`.

**Pros:** Simpler, faster startup (no SSE build phase), fewer moving parts.
**Cons:** Requires token management (can use a read-only token or IBM IAM).

#### Option B: Binder-Compatible Wrapper

Deploy a thin API layer that mimics the Binder `/build/` SSE endpoint but
actually just returns the Code Engine app URL. This requires zero changes to
the existing thebelab integration code.

**Pros:** No frontend changes at all.
**Cons:** Extra component to maintain, unnecessary complexity.

**Recommendation:** Option A. The frontend changes are minimal (~20 lines in
`jupyter.ts` + ~10 lines in `ExecutableCode/index.tsx`), and we eliminate the
SSE build protocol entirely.

### Changes Required

| File | Change |
|------|--------|
| `src/config/jupyter.ts` | Add Code Engine URL for `github-pages` environment |
| `src/components/ExecutableCode/index.tsx` | Skip Binder SSE when `baseUrl` is set |
| `docusaurus.config.ts` | Remove Binder URL from site config (optional) |
| `.github/workflows/deploy.yml` | Add image build + push to IBM CR |
| `.github/workflows/binder.yml` | Remove (no longer needed) |
| `binder/Dockerfile` | Minor: add CORS headers for Code Engine |

### Session Management

The existing session-reuse logic (`ensureBinderSession`, 8-min idle timeout)
can be simplified. Code Engine handles scaling automatically — each user gets a
container instance that stays warm for the configured timeout. The session
token can be stored the same way (sessionStorage).

For multi-user isolation, each request gets routed to a container instance.
Code Engine handles this natively via its Knative-based routing.

## Cost Estimate

### Per-Instance Pricing (2 vCPU, 4 GB RAM)

| Resource | Rate | Per Hour | Per Month (730h) |
|----------|------|----------|-----------------|
| CPU | $0.00003431/vCPU-s | 2 × 3600 × $0.00003431 = **$0.247** | $180.30 |
| Memory | $0.00000356/GB-s | 4 × 3600 × $0.00000356 = **$0.051** | $37.40 |
| **Total per instance** | | **$0.298/hr** | **$217.70** |

### Free Tier (per month)

- 100,000 vCPU-seconds = **~13.9 hours** at 2 vCPU
- 200,000 GB-seconds = **~13.9 hours** at 4 GB RAM
- 100,000 HTTP requests

**The free tier covers ~14 hours of kernel time per month at no cost.**

### Realistic Usage Scenarios

| Scenario | Active hrs/month | Instances | Monthly Cost |
|----------|-----------------|-----------|-------------|
| Light (docs dev) | 20 hrs | 1 | **~$1.78** (after free tier) |
| Moderate (10 users/day) | 100 hrs | 1-2 avg | **~$25.70** |
| Heavy (launch/workshop) | 300 hrs | 3-5 avg | **~$250–440** |

**Key insight:** Scale-to-zero means you only pay when someone is actually
running code. Most of the time, the site serves static content at zero cost.

### Comparison with Alternatives

| Service | Cost/hr (2vCPU/4GB) | Scale to Zero | Cold Start |
|---------|-------------------|---------------|------------|
| **IBM Code Engine** | **$0.30** | Yes | ~5-15s |
| mybinder.org | Free | N/A | 30s–5min |
| AWS Lambda + EFS | ~$0.20 | Yes | 10-30s |
| Google Cloud Run | ~$0.25 | Yes | 5-15s |
| Self-hosted (EC2/VM) | ~$0.10 | No (always on) | 0s |

## Cold Start Mitigation

Code Engine cold starts are 5–15 seconds (pulling a ~3 GB Qiskit image). To
reduce this:

1. **Min instances = 1** during business hours via scheduled scaling — adds
   ~$0.30/hr but eliminates cold starts. Could be toggled via cron.
2. **Smaller image** — strip unused packages, use multi-stage build. Could
   reduce to ~1.5 GB.
3. **Pre-warmed pool** — set min-scale=1 permanently (~$217/month) for
   instant response. Only justified at high traffic.

## Security Considerations

- **Token rotation** — Jupyter token should be rotated periodically and stored
  as a GitHub secret / IBM Secrets Manager value.
- **CORS** — Configure `Access-Control-Allow-Origin` for `*.doqumentation.org`.
- **Network policy** — Code Engine supports private networking; the Jupyter
  server should only accept connections from the site's domain.
- **Resource limits** — CPU/memory caps prevent abuse. Code Engine enforces
  these at the container level.
- **No persistent storage** — Each container is ephemeral (matching current
  Binder behavior). User notebooks are not saved server-side.

## Migration Path

1. **Phase 1** — Deploy Code Engine app alongside Binder (A/B or fallback).
   Add `environment: 'code-engine'` detection in `jupyter.ts`.
2. **Phase 2** — Make Code Engine the default for `github-pages`. Keep Binder
   as fallback (configurable in Settings page).
3. **Phase 3** — Remove Binder integration and `binder.yml` workflow once
   stable.

## Open Questions

- [ ] IBM Cloud account — use existing org account or create dedicated one?
- [ ] Region selection — `us-south`, `eu-de`, or multi-region?
- [ ] Authentication — simple token vs. IBM IAM-based per-user auth?
- [ ] Should we keep Binder as a permanent fallback or remove it entirely?
- [ ] Budget cap — set a monthly spending alert/limit?
