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

Runs on port 9091 (env SSE_PORT to override); nginx reverse-proxies /build/ here.

Implementation: tornado async (single event loop, no threads). The earlier
threaded version (ThreadingMixIn + BaseHTTPRequestHandler) hit GIL contention
around 80-100 concurrent SSE requests, surfacing as "SSE stream ended without
ready event" failures during 12 vCPU stress tests at 100+ concurrent users.
Tornado is already in the image (Jupyter Server runs on it), so no new deps.
"""

import asyncio
import json
import os
import signal
import time
from datetime import datetime, timezone

import tornado.web
import tornado.ioloop
import tornado.httpclient
import tornado.iostream


CORS_ORIGIN = os.environ.get('CORS_ORIGIN', 'https://doqumentation.org')
JUPYTER_PORT = int(os.environ.get('JUPYTER_PORT', '8888'))
SSE_DEFAULT_PORT = '9091'  # Avoid 9090 — Jupyter extensions may bind it
JUPYTER_READY_TIMEOUT = 30  # seconds to wait for Jupyter to become ready
JUPYTER_POLL_INTERVAL = 0.5  # seconds between readiness checks

# In-memory counters (single-threaded event loop, no locks needed)
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
    """Read memory usage. Returns (used_mb, total_mb) or (None, None).

    Prefers cgroup v2 (memory.current / memory.max) which reflects the
    container's actual limit. Falls back to /proc/meminfo (host view).
    On Code Engine, the cgroup limit is the only meaningful number — the
    host /proc/meminfo shows the entire Kubernetes node's RAM (~62 GB),
    not the pod's allocation (~4 GB).
    """
    # Try cgroup v2 first
    try:
        with open('/sys/fs/cgroup/memory.current') as f:
            current = int(f.read().strip())
        with open('/sys/fs/cgroup/memory.max') as f:
            max_str = f.read().strip()
        if max_str != 'max':
            total = int(max_str)
            return (round(current / 1024 / 1024), round(total / 1024 / 1024))
    except (FileNotFoundError, ValueError, PermissionError):
        pass
    # Fall back to /proc/meminfo (host view, less useful in containers)
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


def _read_loadavg():
    """Read system load averages from /proc/loadavg. Returns (1m, 5m, 15m) or (None, None, None)."""
    try:
        with open('/proc/loadavg') as f:
            parts = f.read().split()
            return (float(parts[0]), float(parts[1]), float(parts[2]))
    except (FileNotFoundError, IndexError, ValueError):
        return (None, None, None)


def _read_cpu_count():
    """Count online CPUs visible to the container. Returns int or None.

    On Code Engine, /proc/cpuinfo reflects the host (not the cgroup limit).
    The CPU *limit* is in cgroup v2's cpu.max — read that for the real value.
    """
    try:
        with open('/sys/fs/cgroup/cpu.max') as f:
            quota_str, period_str = f.read().split()
            if quota_str == 'max':
                # No quota — fall through to /proc count
                raise ValueError
            quota = int(quota_str)
            period = int(period_str)
            return max(1, round(quota / period, 2))
    except (FileNotFoundError, ValueError, IndexError):
        pass
    try:
        return os.cpu_count()
    except Exception:
        return None


async def _jupyter_is_ready_async(http_client: tornado.httpclient.AsyncHTTPClient) -> bool:
    """Check if Jupyter server is responding on its local port. Async."""
    token = os.environ.get('JUPYTER_TOKEN', '')
    url = f'http://127.0.0.1:{JUPYTER_PORT}/api/status?token={token}'
    try:
        resp = await http_client.fetch(url, request_timeout=2, raise_error=False)
        return resp.code == 200
    except Exception:
        return False


class BuildHandler(tornado.web.RequestHandler):
    """Handle GET /build/* with SSE events. Async, single coroutine per request."""

    def set_default_headers(self):
        # CORS — set on every response from this handler
        self.set_header('Access-Control-Allow-Origin', CORS_ORIGIN)

    async def get(self, _tail=''):
        # Set SSE headers
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
        self.set_header('Connection', 'keep-alive')

        token = os.environ.get('JUPYTER_TOKEN', '')

        # Determine the public URL for this server from the Host header.
        # Always use https — CE terminates TLS at the edge, so internal
        # X-Forwarded-Proto may be 'http' even though clients use https.
        host = self.request.headers.get('Host', 'localhost:8080')
        base_url = f'https://{host}'

        global _total_sse_connections
        _total_sse_connections += 1
        _log_event("sse_connect", total=_total_sse_connections)

        http_client = tornado.httpclient.AsyncHTTPClient()

        try:
            # Phase 1: connecting (immediate)
            await self._send_event({'phase': 'connecting'})
            await asyncio.sleep(0.3)

            # Phase 2: launching, then poll Jupyter for readiness
            await self._send_event({'phase': 'launching'})
            deadline = asyncio.get_event_loop().time() + JUPYTER_READY_TIMEOUT
            while not await _jupyter_is_ready_async(http_client):
                if asyncio.get_event_loop().time() > deadline:
                    await self._send_event(
                        {'phase': 'failed',
                         'message': 'Jupyter server did not become ready in time'}
                    )
                    return
                await asyncio.sleep(JUPYTER_POLL_INTERVAL)

            # Phase 3: ready (final event includes URL and token)
            await self._send_event(
                {'phase': 'ready', 'url': base_url + '/', 'token': token}
            )
        except (tornado.iostream.StreamClosedError, ConnectionResetError):
            # Client disconnected mid-stream — nothing to do
            pass

    async def _send_event(self, event: dict):
        """Write a single SSE event and flush."""
        line = f'data: {json.dumps(event)}\n\n'
        self.write(line)
        await self.flush()

    async def options(self, _tail=''):
        """CORS preflight."""
        self.set_status(204)
        self.set_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.set_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')


class HealthHandler(tornado.web.RequestHandler):
    """Lightweight health check — no auth required."""

    def set_default_headers(self):
        self.set_header('Access-Control-Allow-Origin', CORS_ORIGIN)

    async def get(self):
        http_client = tornado.httpclient.AsyncHTTPClient()
        if await _jupyter_is_ready_async(http_client):
            self.set_header('Content-Type', 'text/plain')
            self.write('ok\n')
        else:
            self.set_status(503)
            self.write('Jupyter not ready')


class StatsHandler(tornado.web.RequestHandler):
    """Return enriched stats for workshop monitoring dashboard."""

    def set_default_headers(self):
        self.set_header('Access-Control-Allow-Origin', CORS_ORIGIN)

    async def get(self):
        global _peak_kernels, _peak_connections
        token = os.environ.get('JUPYTER_TOKEN', '')
        result = {
            'kernels': 0, 'kernels_busy': 0, 'connections': 0,
            'uptime_seconds': round(time.time() - _process_start_time),
            'memory_mb': None, 'memory_total_mb': None,
            'load_1m': None, 'load_5m': None, 'load_15m': None,
            'cpu_count': None,
            'peak_kernels': _peak_kernels,
            'peak_connections': _peak_connections,
            'total_sse_connections': _total_sse_connections,
            'status': 'unavailable',
        }

        http_client = tornado.httpclient.AsyncHTTPClient()
        try:
            # Fetch Jupyter status (connections, started time, kernel count)
            status_url = f'http://127.0.0.1:{JUPYTER_PORT}/api/status?token={token}'
            status_resp = await http_client.fetch(
                status_url, request_timeout=2, raise_error=False
            )
            if status_resp.code == 200:
                status = json.loads(status_resp.body)
                result['connections'] = status.get('connections', 0)
                result['kernels'] = status.get('kernels', 0)
                # Compute uptime from Jupyter's started timestamp
                started = status.get('started', '')
                if started:
                    try:
                        start_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
                        result['uptime_seconds'] = round(
                            (datetime.now(timezone.utc) - start_dt).total_seconds()
                        )
                    except (ValueError, TypeError):
                        pass

            # Fetch kernel list for busy count
            kernels_url = f'http://127.0.0.1:{JUPYTER_PORT}/api/kernels?token={token}'
            kernels_resp = await http_client.fetch(
                kernels_url, request_timeout=2, raise_error=False
            )
            if kernels_resp.code == 200:
                kernels = json.loads(kernels_resp.body)
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

        # Read system memory (cgroup-aware)
        used_mb, total_mb = _read_memory_mb()
        result['memory_mb'] = used_mb
        result['memory_total_mb'] = total_mb

        # Read CPU load averages and effective CPU count (cgroup-aware)
        load_1m, load_5m, load_15m = _read_loadavg()
        result['load_1m'] = load_1m
        result['load_5m'] = load_5m
        result['load_15m'] = load_15m
        result['cpu_count'] = _read_cpu_count()

        # Log high memory warning (>80%)
        if used_mb and total_mb and total_mb > 0 and used_mb > 0.8 * total_mb:
            _log_event("high_memory", used_mb=used_mb, total_mb=total_mb,
                       pct=round(100 * used_mb / total_mb))

        # Log high CPU warning (1m load > cpu_count, i.e., saturated)
        if load_1m is not None and result['cpu_count']:
            if load_1m > result['cpu_count']:
                _log_event("high_cpu", load_1m=load_1m,
                           cpu_count=result['cpu_count'])

        self.set_header('Content-Type', 'application/json')
        self.set_header('Cache-Control', 'no-cache')
        self.write(json.dumps(result))

    async def options(self):
        """CORS preflight."""
        self.set_status(204)
        self.set_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.set_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')


def make_app() -> tornado.web.Application:
    return tornado.web.Application([
        (r'/build/?(.*)', BuildHandler),
        (r'/health', HealthHandler),
        (r'/stats', StatsHandler),
    ])


def main():
    port = int(os.environ.get('SSE_PORT', SSE_DEFAULT_PORT))
    app = make_app()
    app.listen(port, address='127.0.0.1')

    loop = tornado.ioloop.IOLoop.current()

    def _shutdown(*_):
        loop.add_callback_from_signal(loop.stop)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    print(f'[SSE] Binder-compatible build endpoint on port {port} (tornado async)')
    loop.start()


if __name__ == '__main__':
    main()
