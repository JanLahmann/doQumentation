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
JUPYTER_READY_TIMEOUT = 30  # seconds to wait for Jupyter to become ready
JUPYTER_POLL_INTERVAL = 0.5  # seconds between readiness checks


def _jupyter_is_ready():
    """Check if Jupyter server is responding on its local port."""
    try:
        url = f'http://127.0.0.1:{JUPYTER_PORT}/api/status'
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

        # Determine the public URL for this server.
        # Code Engine sets CE_APP to the app URL; fall back to Host header.
        ce_app = os.environ.get('CE_APP', '')
        if ce_app:
            base_url = ce_app.rstrip('/')
        else:
            host = self.headers.get('Host', 'localhost:8080')
            scheme = self.headers.get('X-Forwarded-Proto', 'http')
            base_url = f'{scheme}://{host}'

        try:
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

    def _send_event(self, event):
        """Write a single SSE event."""
        line = f'data: {json.dumps(event)}\n\n'
        self.wfile.write(line.encode())
        self.wfile.flush()

    def do_OPTIONS(self):
        """Handle CORS preflight for /build paths only."""
        if not self.path.startswith('/build'):
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
    port = int(os.environ.get('SSE_PORT', '9090'))
    server = ThreadingHTTPServer(('127.0.0.1', port), SSEBuildHandler)
    signal.signal(signal.SIGTERM, lambda sig, frame: server.shutdown())
    print(f'[SSE] Binder-compatible build endpoint on port {port}')
    server.serve_forever()


if __name__ == '__main__':
    main()
