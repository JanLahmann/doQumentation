#!/bin/bash
#
# docker-entrypoint.sh — Runtime setup for the doQumentation Jupyter container
#
# Generates (or accepts) a Jupyter token, writes Jupyter config,
# patches nginx to inject the Authorization header, and launches supervisord.
#

set -e

# ── Token setup ──
# Accept JUPYTER_TOKEN from environment, or generate a random 32-char hex token
if [ -z "$JUPYTER_TOKEN" ]; then
  JUPYTER_TOKEN=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
fi

# Validate token: safe characters only, minimum 8 chars
if [[ ! "$JUPYTER_TOKEN" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo "ERROR: JUPYTER_TOKEN must contain only letters, numbers, dashes, and underscores."
  exit 1
fi
if [ ${#JUPYTER_TOKEN} -lt 8 ]; then
  echo "ERROR: JUPYTER_TOKEN must be at least 8 characters long."
  exit 1
fi

# ── CORS origin allowlist ──
# CORS_ORIGIN is a comma-separated list of allowed browser origins, so this
# self-contained image can be reached at several addresses — e.g. an offline
# Pi published (host 8080 -> container :80) as both rasqberry.local:8080 and
# <dhcp-ip>:8080. Default: http://localhost:8080 (single-user local access,
# unchanged behavior).
#
# Scheme policy (enforced below): https:// for any host (managed / TLS tier);
# http:// only for LAN/loopback/.local/single-label/private-IP hosts (isolated
# offline tier) — a CORS-policy allowance on a trusted internet-less venue LAN,
# not a transport hole (a public CA can't issue for a .local name or a private
# IP, and ACME/self-signed aren't practical there).
CORS_ORIGIN="${CORS_ORIGIN:-http://localhost:8080}"

# Validate every entry. Fails fast (non-zero exit) with a clear message.
CORS_ORIGIN="$CORS_ORIGIN" python3 - <<'VALIDATE' || exit 1
import ipaddress, os, re, sys

origins = [o.strip() for o in os.environ.get("CORS_ORIGIN", "").split(",") if o.strip()]
if not origins:
    sys.exit("ERROR: CORS_ORIGIN is empty.")

def host_is_lan(host):
    h = host.lower()
    # A .local name or a single-label hostname cannot be a public FQDN.
    if h.endswith(".local") or "." not in h:
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local

for o in origins:
    m = re.match(r"^(https?)://([A-Za-z0-9.\-]+)(?::(\d+))?$", o)
    if not m:
        sys.exit(f"ERROR: CORS_ORIGIN entry '{o}' must be http(s)://host[:port] with no path.")
    scheme, host, _ = m.groups()
    if scheme == "http" and not host_is_lan(host):
        sys.exit(
            f"ERROR: CORS_ORIGIN entry '{o}' uses http:// with a non-LAN host. "
            "http:// is permitted only for LAN/loopback/.local hosts (offline tier); "
            "use https:// for internet-facing origins."
        )
VALIDATE

# Compute the Jupyter allow_origin config line. One origin -> exact-match
# allow_origin (unchanged default). Multiple -> allow_origin_pat, an anchored
# ^(?:...)$ regex OR of the re.escape'd entries. jupyter_server matches
# allow_origin_pat with re.match(), so the trailing $ is required to block
# prefix attacks (…:8080.evil.com). Built here (not in the unquoted heredoc
# below) so bash doesn't mangle the regex; injected as a pre-expanded value.
CORS_CONFIG=$(CORS_ORIGIN="$CORS_ORIGIN" python3 - <<'GEN'
import os, re
origins = [o.strip() for o in os.environ.get("CORS_ORIGIN", "http://localhost:8080").split(",") if o.strip()]
if len(origins) == 1:
    print(f"c.ServerApp.allow_origin = {origins[0]!r}")
else:
    pat = "^(?:" + "|".join(re.escape(o) for o in origins) + ")$"
    print(f"c.ServerApp.allow_origin_pat = {pat!r}")
GEN
)

# ── Write Jupyter config with real token ──
# Note: /home/jovyan/.jupyter is pre-created in the Dockerfile
JUPYTER_DIR="/home/jovyan/.jupyter"
cat > "$JUPYTER_DIR/jupyter_server_config.py" << PYEOF
# doQumentation — Jupyter Server Configuration
# Generated at container startup by docker-entrypoint.sh

c.ServerApp.token = "${JUPYTER_TOKEN}"
c.ServerApp.password = ""
${CORS_CONFIG}
c.ServerApp.allow_remote_access = True
c.ServerApp.ip = "0.0.0.0"
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.root_dir = "/home/jovyan/notebooks"

# XSRF disabled — thebelab 0.4.0 cannot send XSRF cookies/headers.
# Token auth via Authorization header is the security boundary instead.
c.ServerApp.disable_check_xsrf = True

# Kernel management — cull idle kernels for stability
c.MappingKernelManager.cull_idle_timeout = 600
c.MappingKernelManager.cull_interval = 120
c.MappingKernelManager.cull_connected = False
PYEOF

# ── Inject token into nginx proxy config ──
# Replace placeholder comments with real Authorization headers
sed -i "s|# __JUPYTER_AUTH__|proxy_set_header Authorization \"token ${JUPYTER_TOKEN}\";|g" \
  /etc/nginx/sites-enabled/default

# ── Print token for users ──
echo ""
echo "========================================"
echo "  Jupyter token: ${JUPYTER_TOKEN}"
echo "========================================"
echo ""
echo "  Website (token injected automatically):"
echo "    http://localhost:8080/"
echo ""
echo "  Direct JupyterLab (token required):"
echo "    http://localhost:8888/?token=${JUPYTER_TOKEN}"
echo ""
echo "  To set a fixed token, restart with:"
echo "    JUPYTER_TOKEN=mytoken docker compose --profile jupyter up"
echo "========================================"
echo ""

# ── Launch supervisord (replaces this shell, becomes PID 1) ──
exec supervisord -c /etc/supervisor/conf.d/services.conf
