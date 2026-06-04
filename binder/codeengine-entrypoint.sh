#!/bin/bash
#
# codeengine-entrypoint.sh — Runtime setup for the Code Engine Jupyter container
#
# Generates (or accepts) a Jupyter token, writes Jupyter config, and
# launches supervisord (nginx + Jupyter + SSE build server).
#

set -e

# ── Token setup ──
# Accept JUPYTER_TOKEN from environment, or generate a random 32-char hex token
if [ -z "$JUPYTER_TOKEN" ]; then
  JUPYTER_TOKEN=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
fi

# Validate token: safe characters only, minimum 32 chars
if [[ ! "$JUPYTER_TOKEN" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo "ERROR: JUPYTER_TOKEN must contain only letters, numbers, dashes, and underscores."
  exit 1
fi
if [ ${#JUPYTER_TOKEN} -lt 32 ]; then
  echo "ERROR: JUPYTER_TOKEN must be at least 32 characters long."
  exit 1
fi

export JUPYTER_TOKEN

# ── CORS origin ──
# Allow configuring the allowed origin for cross-origin requests.
# Default: allow doqumentation.org; override with CORS_ORIGIN env var.
CORS_ORIGIN="${CORS_ORIGIN:-https://doqumentation.org}"

# Validate CORS_ORIGIN: must be an https:// URL with safe characters only
if [[ ! "$CORS_ORIGIN" =~ ^https://[a-zA-Z0-9._-]+(:[0-9]+)?$ ]]; then
  echo "ERROR: CORS_ORIGIN must be an https:// URL with safe characters (got: '$CORS_ORIGIN')."
  exit 1
fi

# ── Write Jupyter config ──
# Note: /home/jovyan/.jupyter is pre-created in the Dockerfile
JUPYTER_DIR="/home/jovyan/.jupyter"
cat > "$JUPYTER_DIR/jupyter_server_config.py" << 'PYEOF'
# doQumentation — Jupyter Server Configuration (Code Engine)
# Generated at container startup by codeengine-entrypoint.sh
import os

c.ServerApp.token = os.environ.get("JUPYTER_TOKEN", "")
c.ServerApp.password = ""
c.ServerApp.allow_origin = os.environ.get("CORS_ORIGIN", "https://doqumentation.org")
c.ServerApp.allow_remote_access = True
c.ServerApp.ip = "127.0.0.1"
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.root_dir = "/home/jovyan"

# XSRF disabled — thebelab 0.4.0 cannot send XSRF cookies/headers.
# Token auth via Authorization header is the security boundary instead.
c.ServerApp.disable_check_xsrf = True

# Kernel management — cull idle kernels to save resources.
# cull_busy=False (default, made explicit): never kill a kernel that's
# actively executing — this would orphan a student mid-cell.
#
# cull_connected=True (was False): ALSO reclaim idle kernels whose websocket
# is still "connected". This is the mitigation for the Jupyter Server
# connections_dict underflow bug: that bug corrupts a kernel's connection
# count so it never reaches 0, and with cull_connected=False such a kernel is
# skipped by the culler forever → monotonic memory creep across a workshop day
# (previously only curable by restarting the pod between sessions). With
# cull_connected=True the culler reclaims it once it's been idle long enough,
# regardless of the (possibly-corrupted) connection count.
#
# To keep the UX cost of cull_connected=True low, the idle timeout is raised
# 300s → 600s: a student reading a notebook between cells for up to 10 minutes
# keeps their kernel + state; only genuinely-idle (or leaked) kernels are
# reclaimed. cull_busy=False still protects anyone mid-execution.
c.MappingKernelManager.cull_idle_timeout = 600
c.MappingKernelManager.cull_interval = 60
c.MappingKernelManager.cull_busy = False
c.MappingKernelManager.cull_connected = True
PYEOF

# ── Print startup info ──
echo ""
echo "========================================"
echo "  doQumentation Jupyter (Code Engine)"
echo "========================================"
echo ""
echo "  Jupyter token: ${JUPYTER_TOKEN:0:4}…(redacted)"
echo "  Port: 8080 (nginx proxy)"
echo "  SSE endpoint: /build/ (Binder-compatible)"
echo "  Health check: /health"
echo ""
echo "  CORS origin: ${CORS_ORIGIN}"
echo "========================================"
echo ""

# ── Launch supervisord (replaces this shell, becomes PID 1) ──
exec supervisord -c /etc/supervisor/conf.d/services.conf
