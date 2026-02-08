# Jupyter Token Auth — Enable authentication for Docker/RasQberry

**Status:** Planned (not yet implemented)
**Created:** 2026-02-08

## Context

The Jupyter container (`Dockerfile.jupyter`) currently disables all authentication:
`token=""`, `allow_unauthenticated_access=True`, `disable_check_xsrf=True`.
This means anyone who can reach port 8888 (or the nginx proxy) can execute arbitrary Python code.

This was done because **thebelab 0.4.0 doesn't pass tokens** when connecting to Jupyter kernels. But there's a clean workaround: **nginx can inject the auth token server-side** into all proxied requests, so thebelab works without changes.

## Deployment scenarios

| Deployment | Jupyter access path | Current auth | After this change |
|---|---|---|---|
| **GitHub Pages** | Binder (external) | N/A | No change |
| **Docker (port 8080)** | Browser → nginx → Jupyter | None | nginx injects token |
| **Docker (port 8888)** | Browser → Jupyter direct | None | Token required (`?token=` or header) |
| **RasQberry Pi** | Browser → Jupyter direct | None | Token required |
| **Custom server** | User-configured | User manages | No change |

## Approach: nginx token injection + configurable `JUPYTER_TOKEN`

**Default token: `rasqberry`** — deterministic, backward compatible, documented.
Users deploying to a network set `JUPYTER_TOKEN=<secret>` via env var.

### How it works

1. Entrypoint script reads `JUPYTER_TOKEN` env var (default: `rasqberry`)
2. Writes `jupyter_server_config.py` with that token
3. Writes nginx config with `proxy_set_header Authorization "token <TOKEN>"`
4. All browser requests through nginx get the token injected server-side → thebelab works
5. Direct port 8888 access requires the token in URL or header

**Why `disable_check_xsrf` stays `True`:** XSRF protection relies on cookies; thebelab doesn't send XSRF headers. Token auth via the Authorization header is the security boundary, not XSRF cookies.

**Why `allow_origin = "*"` stays:** Needed for direct 8888 access from a different port (e.g., site on 8080, Lab on 8888).

---

## Step 1: Create `docker-entrypoint.sh`

New file. Reads `JUPYTER_TOKEN` env var, configures nginx and Jupyter at runtime, starts supervisord.

```bash
#!/bin/sh
TOKEN="${JUPYTER_TOKEN:-rasqberry}"

# Write Jupyter config with token
cat > /root/.jupyter/jupyter_server_config.py << EOF
c.ServerApp.token = "$TOKEN"
c.ServerApp.password = ""
c.ServerApp.allow_origin = "*"
c.ServerApp.allow_remote_access = True
c.ServerApp.ip = "0.0.0.0"
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.disable_check_xsrf = True
EOF

# Inject token into nginx proxy headers
sed -i "s/__JUPYTER_TOKEN__/$TOKEN/g" /etc/nginx/sites-enabled/default

echo "============================================"
echo " Jupyter token: $TOKEN"
echo " Site:     http://localhost:80"
echo " Jupyter:  http://localhost:8888/?token=$TOKEN"
echo "============================================"

exec supervisord -c /etc/supervisor/conf.d/services.conf
```

## Step 2: Update `nginx.conf`

Add `proxy_set_header Authorization` with a placeholder token to both proxy locations.

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8888;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header Authorization "token __JUPYTER_TOKEN__";
}

location /terminals/ {
    proxy_pass http://127.0.0.1:8888;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header Authorization "token __JUPYTER_TOKEN__";
}
```

The `__JUPYTER_TOKEN__` placeholder is replaced by the entrypoint script at container startup.

## Step 3: Update `Dockerfile.jupyter`

- Remove inline Jupyter config (entrypoint handles it at runtime)
- Keep supervisord config inline (it doesn't change)
- Remove `allow_unauthenticated_access` and `IdentityProvider.token` (not needed with real token)
- Add `COPY docker-entrypoint.sh` and `ENTRYPOINT`
- Add `ENV JUPYTER_TOKEN=rasqberry` as documented default

Key changes:
```dockerfile
ENV JUPYTER_TOKEN=rasqberry

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
```

## Step 4: Update `docker-compose.yml`

- Add `JUPYTER_TOKEN` env var (with comment about changing for network exposure)
- Keep port 8888 exposed but document it requires the token

```yaml
jupyter:
  build:
    context: .
    dockerfile: Dockerfile.jupyter
  ports:
    - "8080:80"
    - "8888:8888"
  environment:
    - JUPYTER_TOKEN=rasqberry  # Change for network-exposed deployments
```

## Step 5: Update `src/config/jupyter.ts`

Docker mode (line 89) currently sets `token: ''` because auth was disabled. Change to `token: 'rasqberry'` so that "Open in JupyterLab" links (which go directly to port 8888) include the token.

```typescript
// Before:
token: isDocker ? '' : 'rasqberry',
// After:
token: 'rasqberry',
```

Both Docker proxy and direct access now use the same default token. Custom config via localStorage overrides this.

---

## Files to create (1)
1. `docker-entrypoint.sh` — runtime config + supervisord startup

## Files to modify (4)
1. `nginx.conf` — add `proxy_set_header Authorization` with placeholder
2. `Dockerfile.jupyter` — use entrypoint, add `ENV JUPYTER_TOKEN`, remove inline Jupyter config
3. `docker-compose.yml` — add `environment: JUPYTER_TOKEN`
4. `src/config/jupyter.ts` — Docker mode token `''` → `'rasqberry'`

## What does NOT change
- `Dockerfile` (lite image) — no Jupyter, no auth needed
- GitHub Pages / Binder — unaffected
- `src/components/ExecutableCode/index.tsx` — thebelab code unchanged, nginx handles auth
- `src/pages/jupyter-settings.tsx` — custom config already supports tokens

## Verification
1. `docker compose up jupyter` — container starts, prints token
2. `curl http://localhost:8080/api/status` → 200 (nginx injects token)
3. `curl http://localhost:8888/api/status` → 403 (no token)
4. `curl -H "Authorization: token rasqberry" http://localhost:8888/api/status` → 200
5. thebelab code execution works on `http://localhost:8080` (nginx injects auth)
6. "Open in Lab" link opens `http://localhost:8888/lab/tree/...?token=rasqberry` → works
7. `JUPYTER_TOKEN=mysecret docker compose up jupyter` — uses custom token
