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

# ── Write Jupyter config with real token ──
JUPYTER_DIR="/home/jupyter/.jupyter"
mkdir -p "$JUPYTER_DIR"
cat > "$JUPYTER_DIR/jupyter_server_config.py" << PYEOF
# doQumentation — Jupyter Server Configuration
# Generated at container startup by docker-entrypoint.sh

c.ServerApp.token = "${JUPYTER_TOKEN}"
c.ServerApp.password = ""
c.ServerApp.allow_origin = "http://localhost:8080"
c.ServerApp.allow_remote_access = True
c.ServerApp.ip = "0.0.0.0"
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.root_dir = "/home/jupyter/notebooks"

# XSRF disabled — thebelab 0.4.0 cannot send XSRF cookies/headers.
# Token auth via Authorization header is the security boundary instead.
c.ServerApp.disable_check_xsrf = True

# Kernel management — cull idle kernels for stability
c.MappingKernelManager.cull_idle_timeout = 600
c.MappingKernelManager.cull_interval = 120
c.MappingKernelManager.cull_connected = False
PYEOF
chown jupyter:jupyter "$JUPYTER_DIR/jupyter_server_config.py"

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
