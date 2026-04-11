#!/usr/bin/env python3
"""
Workshop stress test — simulate concurrent users running Qiskit notebooks.

Modes:
  Single instance:  Find the capacity limit of one CE instance.
  Workshop pool:    End-to-end rehearsal across multiple instances.
  Failover:         Simulate an instance going down mid-test.

Each simulated user:
  1. Connects via SSE /build/ endpoint
  2. Starts a Jupyter kernel (POST /api/kernels)
  3. Executes cells via WebSocket (/api/kernels/{id}/channels)
  4. Idles between cells (simulates reading time)
  5. Shuts down kernel (DELETE /api/kernels/{id})

Dependencies: pip install aiohttp websockets
"""

import argparse
import asyncio
import base64
import json
import random
import statistics
import sys
import time

try:
    import aiohttp
except ImportError:
    print("Error: aiohttp required. Install: pip install aiohttp")
    sys.exit(1)

try:
    import websockets
except ImportError:
    print("Error: websockets required. Install: pip install websockets")
    sys.exit(1)


# Representative Qiskit workload — 5-qubit random circuit with simulator
QISKIT_CELL = """\
from qiskit.circuit.random import random_circuit
from qiskit_aer import AerSimulator
qc = random_circuit(5, 3, measure=True)
result = AerSimulator().run(qc, shots=1024).result()
print(result.get_counts())
"""

# Lightweight cell for quick tests
SIMPLE_CELL = "print('hello from stress test')"


async def get_stats(session: aiohttp.ClientSession, url: str) -> dict:
    """Query /stats endpoint on an instance.

    The doQumentation CE container's SSE shim exposes a rich /stats endpoint
    (kernels, kernels_busy, connections, peak_*, memory_mb, memory_total_mb,
    load_1m/5m/15m, cpu_count, uptime_seconds). Falls back to {} on error.
    """
    try:
        async with session.get(f"{url.rstrip('/')}/stats",
                               timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception:
        pass
    return {}


def _format_stats(stats: dict) -> str:
    """Render a /stats dict as a one-line summary for the ramp output.

    Prefers peak_* fields (high-water marks) since /stats is queried after
    the run finishes — instantaneous k/conn would always be 0.
    """
    if not stats:
        return "stats=offline"
    parts = []
    peak_k = stats.get("peak_kernels")
    if peak_k is not None:
        parts.append(f"peak_k={peak_k}")
    peak_c = stats.get("peak_connections")
    if peak_c is not None:
        parts.append(f"peak_conn={peak_c}")
    total_sse = stats.get("total_sse_connections")
    if total_sse is not None:
        parts.append(f"sse_total={total_sse}")
    if stats.get("memory_mb") is not None and stats.get("memory_total_mb"):
        pct = round(100 * stats["memory_mb"] / stats["memory_total_mb"])
        parts.append(f"mem={stats['memory_mb']}/{stats['memory_total_mb']}MB({pct}%)")
    if stats.get("load_1m") is not None and stats.get("cpu_count"):
        parts.append(f"load={stats['load_1m']:.2f}/{stats['cpu_count']}cpu")
    return " ".join(parts) if parts else "stats=empty"


async def connect_sse(session: aiohttp.ClientSession, url: str, token: str) -> tuple[str, str]:
    """Connect via SSE /build/ and return (server_url, token)."""
    build_url = f"{url}/build/gh/placeholder"
    async with session.get(build_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
        async for line in resp.content:
            text = line.decode().strip()
            if text.startswith("data: "):
                data = json.loads(text[6:])
                if data.get("phase") == "ready":
                    return data["url"], data.get("token", token)
                if data.get("phase") == "failed":
                    raise RuntimeError(f"SSE build failed: {data}")
    raise RuntimeError("SSE stream ended without ready event")


async def start_kernel(session: aiohttp.ClientSession, url: str, token: str) -> str:
    """Start a kernel and return its ID."""
    headers = {"Authorization": f"token {token}"} if token else {}
    async with session.post(
        f"{url}api/kernels",
        headers=headers,
        json={"name": "python3"},
        timeout=aiohttp.ClientTimeout(total=60),
    ) as resp:
        if resp.status != 201:
            raise RuntimeError(f"Kernel start failed: {resp.status}")
        data = await resp.json()
        return data["id"]


class KernelSession:
    """One persistent WebSocket to a Jupyter kernel, supporting multiple cells.

    Real browser clients (thebelab, JupyterLab) open ONE websocket per kernel
    and reuse it across many cell executions. The earlier per-cell connect
    pattern inflated latencies by ~150-250ms per cell (handshake + Jupyter
    'Connecting to kernel' setup) and triggered Jupyter 'No session ID'
    warnings on every cell. This class matches real-client behavior.
    """

    def __init__(self, base_url: str, kernel_id: str, token: str):
        ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
        self.ws_url = f"{ws_base}api/kernels/{kernel_id}/channels?token={token}"
        # session_id is per-kernel, stable across cells (matches real clients,
        # silences Jupyter's "No session ID specified" warning)
        self.session_id = f"stress-{random.randint(0, 0xFFFFFFFF):08x}"
        self.ws = None

    async def __aenter__(self):
        self.ws = await websockets.connect(self.ws_url, close_timeout=5)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:
                pass

    async def execute(self, code: str) -> float:
        """Execute one cell on this kernel, return wall time in seconds."""
        msg_id = f"{self.session_id}-{random.randint(0, 0xFFFF):04x}"
        execute_msg = {
            "header": {
                "msg_id": msg_id,
                "msg_type": "execute_request",
                "username": "stress-test",
                "session": self.session_id,
                "version": "5.3",
            },
            "parent_header": {},
            "metadata": {},
            "content": {
                "code": code,
                "silent": False,
                "store_history": False,
                "user_expressions": {},
                "allow_stdin": False,
                "stop_on_error": True,
            },
            "buffers": [],
            "channel": "shell",
        }
        start = time.monotonic()
        await self.ws.send(json.dumps(execute_msg))
        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=120)
            reply = json.loads(raw)
            if (
                reply.get("msg_type") == "execute_reply"
                and reply.get("parent_header", {}).get("msg_id") == msg_id
            ):
                return time.monotonic() - start


async def shutdown_kernel(session: aiohttp.ClientSession, url: str, token: str, kernel_id: str):
    """Delete a kernel."""
    headers = {"Authorization": f"token {token}"} if token else {}
    try:
        async with session.delete(
            f"{url}api/kernels/{kernel_id}",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            pass  # 204 expected
    except Exception:
        pass


async def simulate_user(
    user_id: int,
    url: str,
    token: str,
    cells_per_user: int,
    idle_between: float,
    use_qiskit: bool,
) -> dict:
    """Simulate one user session. Returns metrics dict."""
    result = {
        "user_id": user_id,
        "instance": url,
        "kernel_started": False,
        "cells_completed": 0,
        "latencies": [],
        "error": None,
    }

    async with aiohttp.ClientSession() as session:
        try:
            # Connect via SSE
            server_url, server_token = await connect_sse(session, url, token)
            if not server_url.endswith("/"):
                server_url += "/"

            # Start kernel
            kernel_id = await start_kernel(session, server_url, server_token)
            result["kernel_started"] = True

            # Execute cells over ONE persistent websocket (matches real
            # browser clients — thebelab/JupyterLab reuse one WS per kernel).
            code = QISKIT_CELL if use_qiskit else SIMPLE_CELL
            async with KernelSession(server_url, kernel_id, server_token) as ks:
                for cell_num in range(cells_per_user):
                    latency = await ks.execute(code)
                    result["latencies"].append(latency)
                    result["cells_completed"] += 1

                    # Idle between cells (simulate reading)
                    if cell_num < cells_per_user - 1 and idle_between > 0:
                        await asyncio.sleep(idle_between)

            # Cleanup
            await shutdown_kernel(session, server_url, server_token, kernel_id)
        except Exception as e:
            result["error"] = str(e)

    return result


def assign_instances(pool: list[str], num_users: int) -> dict[int, str]:
    """Randomly assign users to instances (mirrors frontend logic)."""
    assignments = {}
    for i in range(num_users):
        assignments[i] = pool[i % len(pool)] if len(pool) > 0 else pool[0]
    # Shuffle to avoid sequential assignment
    user_ids = list(assignments.keys())
    random.shuffle(user_ids)
    shuffled = {}
    for idx, uid in enumerate(user_ids):
        shuffled[uid] = pool[idx % len(pool)]
    return shuffled


async def run_single_instance(args):
    """Single-instance capacity test with ramp."""
    user_counts = [int(x) for x in args.users.split(",")]
    print(f"Single-instance test: {args.url}")
    print(f"Ramp: {user_counts} users, {args.cells_per_user} cells each, {args.idle_between}s idle")
    print()

    for count in user_counts:
        print(f"--- {count} users ---")
        tasks = [
            simulate_user(i, args.url, args.token, args.cells_per_user, args.idle_between, not args.simple)
            for i in range(count)
        ]
        results = await asyncio.gather(*tasks)

        kernels_ok = sum(1 for r in results if r["kernel_started"])
        all_latencies = [lat for r in results for lat in r["latencies"]]
        failures = sum(1 for r in results if r["error"])
        avg_lat = statistics.mean(all_latencies) if all_latencies else 0
        p95_lat = sorted(all_latencies)[int(len(all_latencies) * 0.95)] if len(all_latencies) > 1 else avg_lat

        # Get instance stats from the SSE shim's /stats endpoint
        async with aiohttp.ClientSession() as session:
            stats = await get_stats(session, args.url)

        print(
            f"  Kernels: {kernels_ok}/{count} | "
            f"Avg latency: {avg_lat:.1f}s | p95: {p95_lat:.1f}s | "
            f"Failures: {failures}"
        )
        if stats:
            print(f"  Pod stats: {_format_stats(stats)}")
        for r in results:
            if r["error"]:
                print(f"    User {r['user_id']}: {r['error'][:80]}")

        if failures > count * 0.5:
            print(f"\n=> Stopping: >50% failure rate at {count} users")
            break

    print(f"\n=> Capacity estimate: ~{kernels_ok} users on this instance")


async def run_workshop(args):
    """Workshop pool end-to-end test."""
    pool = args.pool.split(",") if args.pool else []
    if args.workshop:
        config = json.loads(base64.b64decode(args.workshop))
        pool = config["pool"]
        if not args.token:
            args.token = config.get("token", "")

    if not pool:
        print("Error: provide --pool or --workshop")
        sys.exit(1)

    num_users = int(args.users.split(",")[0]) if "," in args.users else int(args.users)
    print(f"Workshop test: {num_users} users across {len(pool)} instances")
    print(f"  {args.cells_per_user} cells/user, {args.idle_between}s idle between cells")
    print()

    # Assign users to instances
    assignments = assign_instances(pool, num_users)

    # Run all users in parallel
    tasks = [
        simulate_user(uid, instance_url, args.token, args.cells_per_user, args.idle_between, not args.simple)
        for uid, instance_url in assignments.items()
    ]
    results = await asyncio.gather(*tasks)

    # Aggregate per instance
    by_instance: dict[str, list] = {url: [] for url in pool}
    for r in results:
        by_instance.setdefault(r["instance"], []).append(r)

    total_failures = 0
    for i, (url, instance_results) in enumerate(by_instance.items(), 1):
        users_on = len(instance_results)
        latencies = [lat for r in instance_results for lat in r["latencies"]]
        failures = sum(1 for r in instance_results if r["error"])
        total_failures += failures
        avg_lat = statistics.mean(latencies) if latencies else 0
        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else avg_lat

        short_url = url.replace("https://", "").split(".")[0]
        print(
            f"  Instance {i} ({short_url}): "
            f"{users_on} users | Avg: {avg_lat:.1f}s | p95: {p95_lat:.1f}s | "
            f"Failures: {failures}"
        )

    connected = sum(1 for r in results if r["kernel_started"])
    print(f"\n  Total: {connected}/{num_users} connected | {total_failures} failures")
    if total_failures == 0:
        print("  Recommendation: OK")
    else:
        print(f"  Recommendation: ISSUES — {total_failures} failure(s), consider adding instances")


def main():
    parser = argparse.ArgumentParser(description="Workshop stress test for Code Engine")
    parser.add_argument("--url", help="Single instance URL (capacity test)")
    parser.add_argument("--pool", help="Comma-separated instance URLs (workshop test)")
    parser.add_argument("--workshop", help="Base64 workshop config (alternative to --pool)")
    parser.add_argument("--token", default="", help="Jupyter token")
    parser.add_argument("--users", default="5", help="User count(s), comma-separated for ramp (e.g. 5,10,15)")
    parser.add_argument("--cells-per-user", type=int, default=3, help="Cells to execute per user")
    parser.add_argument("--idle-between", type=float, default=5, help="Seconds idle between cells")
    parser.add_argument("--simple", action="store_true", help="Use simple print() instead of Qiskit workload")
    args = parser.parse_args()

    if args.url:
        asyncio.run(run_single_instance(args))
    elif args.pool or args.workshop:
        asyncio.run(run_workshop(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
