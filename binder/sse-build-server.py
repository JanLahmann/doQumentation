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
import time
from http.server import HTTPServer, BaseHTTPRequestHandler


class SSEBuildHandler(BaseHTTPRequestHandler):
    """Handle GET /build/* with SSE events."""

    def do_GET(self):
        if not self.path.startswith('/build'):
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
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

        phases = [
            {'phase': 'connecting'},
            {'phase': 'launching'},
            {'phase': 'ready', 'url': base_url + '/', 'token': token},
        ]

        for event in phases:
            line = f'data: {json.dumps(event)}\n\n'
            self.wfile.write(line.encode())
            self.wfile.flush()
            # Small delay between phases so the UI can show progress
            if event['phase'] != 'ready':
                time.sleep(0.3)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def log_message(self, format, *args):
        """Suppress per-request logging (supervisord captures stdout)."""
        pass


def main():
    port = int(os.environ.get('SSE_PORT', '9090'))
    server = HTTPServer(('127.0.0.1', port), SSEBuildHandler)
    print(f'[SSE] Binder-compatible build endpoint on port {port}')
    server.serve_forever()


if __name__ == '__main__':
    main()
