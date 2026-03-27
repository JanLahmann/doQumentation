#!/usr/bin/env python3
"""
Binder-compatible SSE /build/ endpoint for IBM Cloud Code Engine.

Mimics the mybinder.org Server-Sent Events protocol so that thebelab's
ensureBinderSession() works without frontend changes. Since the container
image is pre-built, phases resolve instantly — no actual build occurs.

Protocol (matches mybinder.org):
  - Event stream on GET /build/<anything>
  - Each event: data: {"phase": "<phase>", ...}\n\n
  - Final event includes "url" and "token" fields

Runs on port 9090; nginx reverse-proxies /build/ here.
"""

import json
import os
import signal
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn


CORS_ORIGIN = os.environ.get('CORS_ORIGIN', 'https://doqumentation.org')
JUPYTER_PORT = int(os.environ.get('JUPYTER_PORT', '8888'))
SSE_DEFAULT_PORT = '9091'  # Avoid 9090 — Jupyter extensions may bind it
JUPYTER_READY_TIMEOUT = 30  # seconds to wait for Jupyter to become ready
JUPYTER_POLL_INTERVAL = 0.5  # seconds between readiness checks

# In-memory counters (GIL-safe for ThreadingMixIn)
_total_sse_connections = 0
_peak_kernels = 0
_peak_connections = 0
_process_start_time = time.time()


def _log_event(event_type, **kwargs):
    """Emit a structured JSON log line to stdout (captured by CE)."""
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "event": event_type, **kwargs}
    print(json.dumps(entry), flush=True)


def _read_memory_mb():
    """Read memory usage from /proc/meminfo. Returns (used_mb, total_mb) or (None, None)."""
    try:
        with open('/proc/meminfo') as f:
            info = {}
            for line in f:
                parts = line.split()
                if parts[0] in ('MemTotal:', 'MemAvailable:'):
                    info[parts[0].rstrip(':')] = int(parts[1])  # kB
            total = info.get('MemTotal', 0)
            avail = info.get('MemAvailable', 0)
            return (round((total - avail) / 1024), round(total / 1024))
    except (FileNotFoundError, KeyError, ValueError):
        return (None, None)


def _jupyter_is_ready():
    """Check if Jupyter server is responding on its local port."""
    try:
        token = os.environ.get('JUPYTER_TOKEN', '')
        url = f'http://127.0.0.1:{JUPYTER_PORT}/api/status?token={token}'
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


class SSEBuildHandler(BaseHTTPRequestHandler):
    """Handle GET /build/* with SSE events."""

    def do_GET(self):
        if self.path == '/health':
            # Lightweight health check — no auth required
            if _jupyter_is_ready():
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'ok\n')
            else:
                self.send_error(503, 'Jupyter not ready')
            return

        if self.path == '/stats':
            self._handle_stats()
            return

        if not self.path.startswith('/build'):
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', CORS_ORIGIN)
        self.end_headers()

        token = os.environ.get('JUPYTER_TOKEN', '')

        # Determine the public URL for this server from the Host header.
        # Always use https — CE terminates TLS at the edge, so internal
        # X-Forwarded-Proto may be 'http' even though clients use https.
        host = self.headers.get('Host', 'localhost:8080')
        base_url = f'https://{host}'

        try:
            global _total_sse_connections
            _total_sse_connections += 1
            _log_event("sse_connect", total=_total_sse_connections)

            # Emit connecting phase
            self._send_event({'phase': 'connecting'})
            time.sleep(0.3)

            # Emit launching phase, then wait for Jupyter to be ready
            self._send_event({'phase': 'launching'})
            deadline = time.monotonic() + JUPYTER_READY_TIMEOUT
            while not _jupyter_is_ready():
                if time.monotonic() > deadline:
                    self._send_event({'phase': 'failed', 'message': 'Jupyter server did not become ready in time'})
                    return
                time.sleep(JUPYTER_POLL_INTERVAL)

            # Jupyter confirmed ready — emit ready phase
            self._send_event({'phase': 'ready', 'url': base_url + '/', 'token': token})
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected mid-stream — nothing to do
            pass

    def _handle_stats(self):
        """Return enriched stats for workshop monitoring dashboard."""
        global _peak_kernels, _peak_connections
        token = os.environ.get('JUPYTER_TOKEN', '')
        result = {
            'kernels': 0, 'kernels_busy': 0, 'connections': 0,
            'uptime_seconds': round(time.time() - _process_start_time),
            'memory_mb': None, 'memory_total_mb': None,
            'peak_kernels': _peak_kernels,
            'peak_connections': _peak_connections,
            'total_sse_connections': _total_sse_connections,
            'status': 'unavailable',
        }
        try:
            # Fetch Jupyter status (connections, started time, kernel count)
            status_url = f'http://127.0.0.1:{JUPYTER_PORT}/api/status?token={token}'
            with urllib.request.urlopen(status_url, timeout=2) as resp:
                status = json.loads(resp.read())
            result['connections'] = status.get('connections', 0)
            result['kernels'] = status.get('kernels', 0)
            # Compute uptime from Jupyter's started timestamp
            started = status.get('started', '')
            if started:
                from datetime import datetime, timezone
                try:
                    start_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
                    result['uptime_seconds'] = round((datetime.now(timezone.utc) - start_dt).total_seconds())
                except (ValueError, TypeError):
                    pass

            # Fetch kernel list for busy count
            kernels_url = f'http://127.0.0.1:{JUPYTER_PORT}/api/kernels?token={token}'
            with urllib.request.urlopen(kernels_url, timeout=2) as resp:
                kernels = json.loads(resp.read())
            result['kernels'] = len(kernels)
            result['kernels_busy'] = sum(
                1 for k in kernels if k.get('execution_state') == 'busy'
            )

            # Update high-water marks
            _peak_kernels = max(_peak_kernels, result['kernels'])
            _peak_connections = max(_peak_connections, result['connections'])
            result['peak_kernels'] = _peak_kernels
            result['peak_connections'] = _peak_connections
            result['status'] = 'ready'
        except Exception:
            pass  # keep unavailable status with counter fields

        # Read system memory (Linux /proc/meminfo)
        used_mb, total_mb = _read_memory_mb()
        result['memory_mb'] = used_mb
        result['memory_total_mb'] = total_mb

        # Log high memory warning (>80%)
        if used_mb and total_mb and total_mb > 0 and used_mb > 0.8 * total_mb:
            _log_event("high_memory", used_mb=used_mb, total_mb=total_mb,
                       pct=round(100 * used_mb / total_mb))

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', CORS_ORIGIN)
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def _send_event(self, event):
        """Write a single SSE event."""
        line = f'data: {json.dumps(event)}\n\n'
        self.wfile.write(line.encode())
        self.wfile.flush()

    def do_OPTIONS(self):
        """Handle CORS preflight for /build and /stats paths."""
        if not (self.path.startswith('/build') or self.path == '/stats'):
            self.send_error(404)
            return
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', CORS_ORIGIN)
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def log_message(self, format, *args):
        """Log errors only; suppress routine request logging."""
        # args[1] is the status code string (e.g. '200', '404')
        if args and len(args) >= 2:
            try:
                code = int(args[1])
                if code >= 400:
                    super().log_message(format, *args)
            except (ValueError, IndexError):
                super().log_message(format, *args)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    port = int(os.environ.get('SSE_PORT', SSE_DEFAULT_PORT))
    server = ThreadingHTTPServer(('127.0.0.1', port), SSEBuildHandler)
    signal.signal(signal.SIGTERM, lambda sig, frame: server.shutdown())
    print(f'[SSE] Binder-compatible build endpoint on port {port}')
    server.serve_forever()


if __name__ == '__main__':
    main()
