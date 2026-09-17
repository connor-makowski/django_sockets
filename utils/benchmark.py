#!/usr/bin/env python
"""
django_sockets Performance Benchmark Suite
==========================================
Measures performance profiles across key subsystems of django_sockets:
1. Pub/Sub Broadcast Latency Distribution
2. Pub/Sub Burst Throughput
3. Payload Size Scaling & Serialization Thresholds
4. Channel Fan-Out Scalability (1-to-N Delivery)
5. Inbound WebSocket Message Dispatch & Thread Concurrency
6. Concurrent Publishing & Shard Contention
7. End-to-End WebSocket ASGI Server (Uvicorn)
8. Authentication Middleware (DRF Token Auth)

Outputs a comprehensive Markdown report with perfectly aligned tables to `benchmark.md`.
"""

import os
import sys
import time
import socket
import asyncio
import json
import statistics
import threading
import platform
import argparse
from pathlib import Path

# Setup Django environment dynamically before importing django_sockets
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "rest_framework",
            "rest_framework.authtoken",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": "file:benchdb?mode=memory&cache=shared",
                "OPTIONS": {
                    "uri": True,
                },
            }
        },
        SECRET_KEY="benchmark-secret-key-django-sockets",
    )
    django.setup()
    from django.core.management import call_command

    call_command("migrate", run_syncdb=True, verbosity=0)

import uvicorn
import websockets
from django.urls import path
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from django_sockets.sockets import BaseSocketServer
from django_sockets.broadcaster import Broadcaster
from django_sockets.utils import ProtocolTypeRouter, URLRouter
from django_sockets.middleware.drf import DRFTokenAuthMiddleware

CACHE_HOST = os.environ.get("CACHE_HOST", "localhost")
CACHE_PORT = int(os.environ.get("CACHE_PORT", "6379"))
HOSTS = [{"address": f"redis://{CACHE_HOST}:{CACHE_PORT}"}]


# ---------------------------------------------------------------------------
# Cache / Redis Management Helpers
# ---------------------------------------------------------------------------


root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))


def is_redis_running(host=CACHE_HOST, port=CACHE_PORT, timeout=0.3):
    """Check if the cache backend is accepting TCP connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ensure_redis():
    """Ensure Valkey/Redis is running, starting local docker container if needed."""
    if is_redis_running():
        return False  # Already running; not started by us

    print("Cache not reachable on localhost:6379. Starting Valkey container...")
    from utils.redis_start import start_redis

    start_redis()
    return True  # Started by us


# ---------------------------------------------------------------------------
# Markdown Table Formatting Helpers (Clean Raw & Rendered Spacing)
# ---------------------------------------------------------------------------


def format_markdown_table(headers, rows, alignments=None):
    """Format a Markdown table where columns are padded to uniform width,

    ensuring pristine readability in both raw text files and rendered viewers.
    """
    str_headers = [str(h) for h in headers]
    str_rows = [[str(cell) for cell in row] for row in rows]
    num_cols = len(str_headers)

    if alignments is None:
        alignments = ["left"] * num_cols

    # Calculate column widths based on maximum contents
    col_widths = [len(str_headers[i]) for i in range(num_cols)]
    for row in str_rows:
        for i in range(num_cols):
            if i < len(row):
                col_widths[i] = max(col_widths[i], len(row[i]))
    col_widths = [max(w, 3) for w in col_widths]

    # Format header row
    header_cells = []
    for i, h in enumerate(str_headers):
        if alignments[i] == "right":
            header_cells.append(h.rjust(col_widths[i]))
        elif alignments[i] == "center":
            header_cells.append(h.center(col_widths[i]))
        else:
            header_cells.append(h.ljust(col_widths[i]))
    header_line = "| " + " | ".join(header_cells) + " |"

    # Format separator row with alignment indicators
    sep_cells = []
    for i, a in enumerate(alignments):
        w = col_widths[i]
        if a == "right":
            sep_cells.append("-" * (w - 1) + ":")
        elif a == "center":
            sep_cells.append(":" + "-" * (w - 2) + ":")
        else:
            sep_cells.append(":" + "-" * (w - 1))
    sep_line = "| " + " | ".join(sep_cells) + " |"

    # Format data rows
    row_lines = []
    for row in str_rows:
        row_cells = []
        for i in range(num_cols):
            val = row[i] if i < len(row) else ""
            if alignments[i] == "right":
                row_cells.append(val.rjust(col_widths[i]))
            elif alignments[i] == "center":
                row_cells.append(val.center(col_widths[i]))
            else:
                row_cells.append(val.ljust(col_widths[i]))
        row_lines.append("| " + " | ".join(row_cells) + " |")

    return "\n".join([header_line, sep_line] + row_lines)


# ---------------------------------------------------------------------------
# Benchmark Suite 1: Pub/Sub Broadcast Latency Distribution
# ---------------------------------------------------------------------------


async def run_benchmark_pubsub_latency(samples=30):
    """Measures single-message round-trip latency through Redis pub/sub to subscriber."""
    print(f"  -> Running Pub/Sub Latency benchmark ({samples} samples)...")
    latencies = []
    event = asyncio.Event()

    async def mock_send(msg):
        t1 = time.perf_counter()
        parsed = json.loads(msg["text"])
        latencies.append((t1 - parsed["t0"]) * 1000.0)
        event.set()

    q = asyncio.Queue()
    server = BaseSocketServer(
        scope={}, receive=q.get, send=mock_send, hosts=HOSTS
    )
    task = asyncio.create_task(server.async_start_listeners())
    await server.async_subscribe("bench_pubsub_latency")
    await asyncio.sleep(0.2)  # warm-up

    for i in range(samples):
        event.clear()
        t0 = time.perf_counter()
        await server.async_broadcast(
            "bench_pubsub_latency", {"id": i, "t0": t0}
        )
        await asyncio.wait_for(event.wait(), timeout=5.0)

    server.__kill__()
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    sorted_lats = sorted(latencies)
    return {
        "samples": len(latencies),
        "min": min(latencies),
        "mean": statistics.mean(latencies),
        "p50": statistics.median(latencies),
        "p90": sorted_lats[int(len(sorted_lats) * 0.90)],
        "p95": sorted_lats[int(len(sorted_lats) * 0.95)],
        "p99": sorted_lats[
            min(int(len(sorted_lats) * 0.99), len(sorted_lats) - 1)
        ],
        "max": max(latencies),
        "stdev": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
    }


# ---------------------------------------------------------------------------
# Benchmark Suite 2: Pub/Sub Burst Throughput
# ---------------------------------------------------------------------------


async def run_benchmark_pubsub_throughput(burst_sizes=(10, 25, 50)):
    """Measures delivery throughput when publishing a burst of messages rapidly."""
    print(f"  -> Running Pub/Sub Burst Throughput benchmark...")
    results = []

    for count in burst_sizes:
        received_timestamps = []
        done_event = asyncio.Event()

        async def mock_send(msg):
            t_recv = time.perf_counter()
            parsed = json.loads(msg["text"])
            received_timestamps.append((t_recv, parsed["t0"]))
            if len(received_timestamps) == count:
                done_event.set()

        q = asyncio.Queue()
        server = BaseSocketServer(
            scope={}, receive=q.get, send=mock_send, hosts=HOSTS
        )
        task = asyncio.create_task(server.async_start_listeners())
        channel = f"bench_burst_{count}"
        await server.async_subscribe(channel)
        await asyncio.sleep(0.2)

        t_start = time.perf_counter()
        for i in range(count):
            t0 = time.perf_counter()
            await server.async_broadcast(channel, {"id": i, "t0": t0})

        await asyncio.wait_for(done_event.wait(), timeout=15.0)
        total_time = time.perf_counter() - t_start

        server.__kill__()
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        latencies = [(tr - ts) * 1000.0 for tr, ts in received_timestamps]
        results.append(
            {
                "count": count,
                "delivered": len(received_timestamps),
                "total_time": total_time,
                "throughput": len(received_timestamps) / total_time,
                "avg_lat": statistics.mean(latencies),
                "p50_lat": statistics.median(latencies),
            }
        )

    return results


# ---------------------------------------------------------------------------
# Benchmark Suite 3: Payload Size Scaling & Serialization Thresholds
# ---------------------------------------------------------------------------


async def run_benchmark_payload_sizes():
    """Evaluates latency and throughput across different message payload sizes,"""
    print(f"  -> Running Payload Size Scaling benchmark...")
    test_specs = [
        ("64 B (Tiny / Ping)", 64, 10),
        ("1 KB (Small Event)", 1024, 10),
        ("64 KB (Medium State)", 64 * 1024, 10),
        ("512 KB (Large Dataset)", 512 * 1024, 5),
        ("1.5 MB (>1MB Cache Bypass)", int(1.5 * 1024 * 1024), 3),
    ]

    event = asyncio.Event()
    latencies = []
    t_send = [0.0]

    async def mock_send(msg):
        t1 = time.perf_counter()
        latencies.append((t1 - t_send[0]) * 1000.0)
        event.set()

    q = asyncio.Queue()
    server = BaseSocketServer(
        scope={}, receive=q.get, send=mock_send, hosts=HOSTS
    )
    task = asyncio.create_task(server.async_start_listeners())
    await server.async_subscribe("bench_payloads")
    await asyncio.sleep(0.2)

    results = []
    for label, byte_size, count in test_specs:
        latencies.clear()
        dummy_str = "x" * byte_size
        payload = {"data": dummy_str}

        for _ in range(count):
            event.clear()
            t_send[0] = time.perf_counter()
            await server.async_broadcast("bench_payloads", payload)
            await asyncio.wait_for(event.wait(), timeout=10.0)

        avg_lat = statistics.mean(latencies)
        p50_lat = statistics.median(latencies)
        sorted_lats = sorted(latencies)
        p95_lat = sorted_lats[int(len(sorted_lats) * 0.95)]
        bandwidth_mb_s = (byte_size / (1024 * 1024)) / (avg_lat / 1000.0)

        results.append(
            {
                "label": label,
                "bytes": byte_size,
                "count": count,
                "min": min(latencies),
                "mean": avg_lat,
                "p50": p50_lat,
                "p95": p95_lat,
                "max": max(latencies),
                "bandwidth_mb_s": bandwidth_mb_s,
            }
        )

    server.__kill__()
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    return results


# ---------------------------------------------------------------------------
# Benchmark Suite 4: Channel Fan-Out Scalability
# ---------------------------------------------------------------------------


async def run_benchmark_fanout(subscriber_counts=(1, 5, 10, 25, 50)):
    """Measures broadcasting from 1 publisher to N subscriber connections."""
    print(f"  -> Running Channel Fan-Out benchmark...")
    num_broadcasts = 5
    results = []

    for num_subs in subscriber_counts:
        received_counts = [0] * num_subs
        delivery_latencies = []
        servers = []
        listener_tasks = []

        for idx in range(num_subs):
            sub_id = idx

            async def make_send(i):
                async def mock_send(msg):
                    t_recv = time.perf_counter()
                    parsed = json.loads(msg["text"])
                    delivery_latencies.append((t_recv - parsed["t0"]) * 1000.0)
                    received_counts[i] += 1

                return mock_send

            q = asyncio.Queue()
            s = BaseSocketServer(
                scope={},
                receive=q.get,
                send=await make_send(idx),
                hosts=HOSTS,
            )
            servers.append(s)
            listener_tasks.append(
                asyncio.create_task(s.async_start_listeners())
            )
            await s.async_subscribe("bench_fanout_channel")

        await asyncio.sleep(0.3)  # warm-up all subscriptions

        t_start = time.perf_counter()
        for m in range(num_broadcasts):
            t0 = time.perf_counter()
            await servers[0].async_broadcast(
                "bench_fanout_channel", {"msg_id": m, "t0": t0}
            )

        # Wait for all subscribers to receive all messages
        start_wait = time.time()
        expected_deliveries = num_subs * num_broadcasts
        while len(delivery_latencies) < expected_deliveries:
            if time.time() - start_wait > 8.0:
                break
            await asyncio.sleep(0.01)
        total_time = time.perf_counter() - t_start

        for s in servers:
            s.__kill__()
        await asyncio.sleep(0.05)
        for t in listener_tasks:
            t.cancel()

        total_delivered = len(delivery_latencies)
        results.append(
            {
                "subscribers": num_subs,
                "broadcasts": num_broadcasts,
                "delivered": total_delivered,
                "total_time": total_time,
                "broadcast_rate": num_broadcasts / total_time,
                "delivery_rate": total_delivered / total_time,
                "mean_lat": (
                    statistics.mean(delivery_latencies)
                    if delivery_latencies
                    else 0.0
                ),
            }
        )

    return results


# ---------------------------------------------------------------------------
# Benchmark Suite 5: Inbound WebSocket Message Dispatch & Thread Creation
# ---------------------------------------------------------------------------


async def run_benchmark_inbound_dispatch(message_counts=(20, 50, 100)):
    """Measures inbound message processing via `__ws_listener_task__` and `run_in_thread`."""
    print(f"  -> Running Inbound WS Message Dispatch benchmark...")
    results = []

    for num_msgs in message_counts:
        received = []
        threads_seen = set()
        done_event = threading.Event()
        max_threads = [0]

        class BenchServer(BaseSocketServer):
            def receive(self, data):
                threads_seen.add(threading.get_ident())
                active = threading.active_count()
                if active > max_threads[0]:
                    max_threads[0] = active
                # Simulate 2ms of business logic / DB read per message
                time.sleep(0.002)
                received.append(data["id"])
                if len(received) == num_msgs:
                    done_event.set()

        async def dummy_send(data):
            pass

        q = asyncio.Queue()
        server = BenchServer(
            scope={}, receive=q.get, send=dummy_send, hosts=HOSTS
        )
        task = asyncio.create_task(server.async_start_listeners())
        await asyncio.sleep(0.1)

        t_start = time.perf_counter()
        for i in range(num_msgs):
            q.put_nowait(
                {"type": "websocket.receive", "text": json.dumps({"id": i})}
            )

        await asyncio.to_thread(done_event.wait, 10.0)
        total_time = time.perf_counter() - t_start

        server.__kill__()
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        rate = len(received) / total_time if total_time > 0 else 0
        results.append(
            {
                "messages": num_msgs,
                "processed": len(received),
                "threads_spawned": len(threads_seen),
                "max_concurrent_threads": max_threads[0],
                "time_ms": total_time * 1000.0,
                "rate": rate,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Benchmark Suite 6: Concurrent Publishing & Shard Contention
# ---------------------------------------------------------------------------


async def run_benchmark_concurrent_publishing(concurrencies=(1, 2, 4, 8)):
    """Measures publishing throughput and latency under concurrent worker coroutines."""
    print(f"  -> Running Concurrent Publishing benchmark...")
    broadcaster = Broadcaster(hosts=HOSTS)
    results = []

    for concurrency in concurrencies:
        messages_per_task = 50
        total_messages = concurrency * messages_per_task

        async def worker(worker_id):
            for i in range(messages_per_task):
                await broadcaster.async_broadcast(
                    "bench_concurrent_channel",
                    {"worker": worker_id, "i": i, "payload": "sample_data"},
                )

        t_start = time.perf_counter()
        tasks = [asyncio.create_task(worker(w)) for w in range(concurrency)]
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - t_start

        throughput = total_messages / total_time
        avg_latency = (total_time / messages_per_task) * 1000.0

        results.append(
            {
                "concurrency": concurrency,
                "total_messages": total_messages,
                "total_time": total_time,
                "throughput": throughput,
                "avg_lat": avg_latency,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Benchmark Suite 7: End-to-End WebSocket ASGI Server (Uvicorn)
# ---------------------------------------------------------------------------


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


async def run_benchmark_e2e_uvicorn():
    """Measures end-to-end WebSocket round-trip ping-pong over real TCP using Uvicorn."""
    print(f"  -> Running End-to-End Uvicorn WebSocket benchmark...")

    class EchoSocketServer(BaseSocketServer):
        def configure(self):
            self.hosts = HOSTS

        def connect(self):
            self.channel_id = "e2e_bench_channel"
            self.subscribe(self.channel_id)

        def receive(self, data):
            self.broadcast(self.channel_id, data)

    app = ProtocolTypeRouter(
        {
            "websocket": URLRouter(
                [
                    path("ws/", EchoSocketServer.as_asgi),
                ]
            )
        }
    )

    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    # Wait for Uvicorn to start listening
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            await asyncio.sleep(0.05)

    uri = f"ws://127.0.0.1:{port}/ws/"
    async with websockets.connect(uri) as ws:
        # Warm-up handshake
        await ws.send(json.dumps({"type": "warmup"}))
        await ws.recv()

        # Sequential round-trip latency
        num_sequential = 20
        seq_latencies = []
        for i in range(num_sequential):
            t0 = time.perf_counter()
            await ws.send(json.dumps({"id": i, "t0": t0}))
            resp = await ws.recv()
            t1 = time.perf_counter()
            seq_latencies.append((t1 - t0) * 1000.0)

        # Burst throughput
        num_burst = 25
        t_burst_start = time.perf_counter()
        for i in range(num_burst):
            await ws.send(json.dumps({"burst_id": i}))
        for _ in range(num_burst):
            await ws.recv()
        burst_duration = time.perf_counter() - t_burst_start

    server.should_exit = True
    await server_task

    sorted_seq = sorted(seq_latencies)
    return {
        "sequential": {
            "samples": len(seq_latencies),
            "min": min(seq_latencies),
            "mean": statistics.mean(seq_latencies),
            "p50": statistics.median(seq_latencies),
            "p95": sorted_seq[int(len(sorted_seq) * 0.95)],
            "max": max(seq_latencies),
            "rate": len(seq_latencies) / (sum(seq_latencies) / 1000.0),
        },
        "burst": {
            "messages": num_burst,
            "duration": burst_duration,
            "throughput": num_burst / burst_duration,
        },
    }


# ---------------------------------------------------------------------------
# Benchmark Suite 8: Authentication Middleware (DRF Token Auth)
# ---------------------------------------------------------------------------


def _setup_bench_user():
    User = get_user_model()
    user, _ = User.objects.get_or_create(username="bench_auth_user")
    token, _ = Token.objects.get_or_create(user=user)
    return user, token.key


async def run_benchmark_auth_middleware(num_lookups=100):
    """Measures DRFTokenAuthMiddleware handshake token lookup latency."""
    print(f"  -> Running DRF Token Auth Middleware benchmark...")
    user, token_key = await asyncio.to_thread(_setup_bench_user)

    async def dummy_app(scope, receive, send):
        pass

    middleware = DRFTokenAuthMiddleware(dummy_app)

    # Warm-up lookup
    res = await middleware.get_user(token_key)
    assert res == user

    # Sequential lookups
    seq_latencies = []
    for _ in range(num_lookups):
        t0 = time.perf_counter()
        await middleware.get_user(token_key)
        t1 = time.perf_counter()
        seq_latencies.append((t1 - t0) * 1000.0)

    # Concurrent lookups
    t_conc_start = time.perf_counter()
    await asyncio.gather(
        *[middleware.get_user(token_key) for _ in range(num_lookups)]
    )
    conc_duration = time.perf_counter() - t_conc_start

    sorted_seq = sorted(seq_latencies)
    return {
        "sequential": {
            "lookups": num_lookups,
            "mean": statistics.mean(seq_latencies),
            "p50": statistics.median(seq_latencies),
            "p95": sorted_seq[int(len(sorted_seq) * 0.95)],
            "max": max(seq_latencies),
            "throughput": num_lookups / (sum(seq_latencies) / 1000.0),
        },
        "concurrent": {
            "lookups": num_lookups,
            "duration": conc_duration,
            "throughput": num_lookups / conc_duration,
            "avg_lat": (conc_duration / num_lookups) * 1000.0,
        },
    }


# ---------------------------------------------------------------------------
# Report Generator (Generates benchmark.md)
# ---------------------------------------------------------------------------


def generate_markdown_report(bench_data, output_path: Path):
    """Assembles all benchmark data into a polished Markdown document with perfectly

    spaced and aligned tables.
    """
    sys_info = bench_data["system"]
    b1 = bench_data["b1_pubsub_latency"]
    b2 = bench_data["b2_pubsub_throughput"]
    b3 = bench_data["b3_payload_sizes"]
    b4 = bench_data["b4_fanout"]
    b5 = bench_data["b5_inbound"]
    b6 = bench_data["b6_concurrent_publish"]
    b7 = bench_data["b7_e2e_uvicorn"]
    b8 = bench_data["b8_auth_middleware"]

    # Table 0: Executive Summary
    t0_headers = [
        "Benchmark Profile",
        "Key Metric",
        "Measured Value",
    ]
    t0_align = ["left", "left", "right"]
    t0_rows = [
        [
            "Pub/Sub Message Latency",
            "P50 Latency",
            f"{b1['p50']:.2f} ms",
        ],
        [
            "Pub/Sub Burst Streaming",
            "Peak Throughput",
            f"{max(r['throughput'] for r in b2):.1f} msg/s",
        ],
        [
            "1.5MB Payload (>1MB)",
            "Bandwidth",
            f"{b3[-1]['bandwidth_mb_s']:.2f} MB/s",
        ],
        [
            "Fan-Out (50 Subscribers)",
            "Delivered Rate",
            f"{b4[-1]['delivery_rate']:.1f} msg/s",
        ],
        [
            "Inbound WS Dispatch",
            "Peak Throughput",
            f"{max(r['rate'] for r in b5):.1f} msg/s",
        ],
        [
            "Concurrent Publishing",
            "Peak Throughput",
            f"{max(r['throughput'] for r in b6):.1f} msg/s",
        ],
        [
            "End-to-End WebSocket (Uvicorn)",
            "Mean Round-Trip",
            f"{b7['sequential']['mean']:.2f} ms",
        ],
        [
            "DRF Token Authentication",
            "Handshake Auth Rate",
            f"{b8['sequential']['throughput']:.1f} auth/s",
        ],
    ]
    t0_md = format_markdown_table(t0_headers, t0_rows, t0_align)

    # Table 1: Pub/Sub Latency Distribution
    t1_headers = [
        "Metric",
        "Pub/Sub Latency (ms)",
    ]
    t1_align = ["left", "right"]
    t1_rows = [
        ["Samples Collected", f"{b1['samples']}"],
        ["Min Latency", f"{b1['min']:.2f} ms"],
        ["Mean Latency", f"{b1['mean']:.2f} ms"],
        ["Median (P50)", f"{b1['p50']:.2f} ms"],
        ["P90 Latency", f"{b1['p90']:.2f} ms"],
        ["P95 Latency", f"{b1['p95']:.2f} ms"],
        ["P99 Latency", f"{b1['p99']:.2f} ms"],
        ["Max Latency", f"{b1['max']:.2f} ms"],
        ["Std Deviation", f"{b1['stdev']:.2f} ms"],
    ]
    t1_md = format_markdown_table(t1_headers, t1_rows, t1_align)

    # Table 2: Burst Throughput
    t2_headers = [
        "Burst Batch Size",
        "Delivered Messages",
        "Total Duration (s)",
        "Throughput (msg/s)",
        "Mean Latency (ms)",
        "Median Latency (ms)",
    ]
    t2_align = ["right", "right", "right", "right", "right", "right"]
    t2_rows = [
        [
            f"{r['count']}",
            f"{r['delivered']}",
            f"{r['total_time']:.3f} s",
            f"{r['throughput']:.1f} msg/s",
            f"{r['avg_lat']:.2f} ms",
            f"{r['p50_lat']:.2f} ms",
        ]
        for r in b2
    ]
    t2_md = format_markdown_table(t2_headers, t2_rows, t2_align)

    # Table 3: Payload Scaling
    t3_headers = [
        "Payload Description",
        "Bytes",
        "Samples",
        "Min (ms)",
        "Mean (ms)",
        "P50 (ms)",
        "P95 (ms)",
        "Max (ms)",
        "Bandwidth (MB/s)",
    ]
    t3_align = [
        "left",
        "right",
        "right",
        "right",
        "right",
        "right",
        "right",
        "right",
        "right",
    ]
    t3_rows = [
        [
            r["label"],
            f"{r['bytes']:,}",
            f"{r['count']}",
            f"{r['min']:.2f}",
            f"{r['mean']:.2f}",
            f"{r['p50']:.2f}",
            f"{r['p95']:.2f}",
            f"{r['max']:.2f}",
            f"{r['bandwidth_mb_s']:.2f}",
        ]
        for r in b3
    ]
    t3_md = format_markdown_table(t3_headers, t3_rows, t3_align)

    # Table 4: Fan-Out
    t4_headers = [
        "Subscribers",
        "Broadcasts Sent",
        "Messages Delivered",
        "Total Time (s)",
        "Broadcast Rate (pub/s)",
        "Fan-Out Delivery Rate (msg/s)",
        "Mean Delivery Latency (ms)",
    ]
    t4_align = ["right", "right", "right", "right", "right", "right", "right"]
    t4_rows = [
        [
            f"{r['subscribers']}",
            f"{r['broadcasts']}",
            f"{r['delivered']}",
            f"{r['total_time']:.3f} s",
            f"{r['broadcast_rate']:.1f} pub/s",
            f"{r['delivery_rate']:.1f} msg/s",
            f"{r['mean_lat']:.2f} ms",
        ]
        for r in b4
    ]
    t4_md = format_markdown_table(t4_headers, t4_rows, t4_align)

    # Table 5: Inbound Dispatch
    t5_headers = [
        "Incoming Messages",
        "Processed",
        "Worker Pool Threads",
        "Max Concurrent Threads",
        "Total Time (ms)",
        "Throughput (msg/s)",
    ]
    t5_align = ["right", "right", "right", "right", "right", "right"]
    t5_rows = [
        [
            f"{r['messages']}",
            f"{r['processed']}",
            f"{r['threads_spawned']}",
            f"{r['max_concurrent_threads']}",
            f"{r['time_ms']:.2f} ms",
            f"{r['rate']:.1f} msg/s",
        ]
        for r in b5
    ]
    t5_md = format_markdown_table(t5_headers, t5_rows, t5_align)

    # Table 6: Concurrent Publishing
    t6_headers = [
        "Concurrency Level",
        "Total Messages",
        "Total Time (s)",
        "Throughput (msg/s)",
        "Avg Latency per Task (ms)",
    ]
    t6_align = ["right", "right", "right", "right", "right"]
    t6_rows = [
        [
            f"{r['concurrency']} worker(s)",
            f"{r['total_messages']}",
            f"{r['total_time']:.3f} s",
            f"{r['throughput']:.1f} msg/s",
            f"{r['avg_lat']:.2f} ms",
        ]
        for r in b6
    ]
    t6_md = format_markdown_table(t6_headers, t6_rows, t6_align)

    # Table 7: E2E Uvicorn
    t7_headers = [
        "Interaction Profile",
        "Count",
        "Min (ms)",
        "Mean (ms)",
        "P50 (ms)",
        "P95 (ms)",
        "Max (ms)",
        "Throughput",
    ]
    t7_align = [
        "left",
        "right",
        "right",
        "right",
        "right",
        "right",
        "right",
        "right",
    ]
    t7_seq = b7["sequential"]
    t7_burst = b7["burst"]
    t7_rows = [
        [
            "Sequential Ping-Pong",
            f"{t7_seq['samples']} reqs",
            f"{t7_seq['min']:.2f}",
            f"{t7_seq['mean']:.2f}",
            f"{t7_seq['p50']:.2f}",
            f"{t7_seq['p95']:.2f}",
            f"{t7_seq['max']:.2f}",
            f"{t7_seq['rate']:.1f} req/s",
        ],
        [
            "Burst Stream",
            f"{t7_burst['messages']} msgs",
            "-",
            "-",
            "-",
            "-",
            f"{t7_burst['duration']*1000:.2f} ms",
            f"{t7_burst['throughput']:.1f} msg/s",
        ],
    ]
    t7_md = format_markdown_table(t7_headers, t7_rows, t7_align)

    # Table 8: Auth Middleware
    t8_headers = [
        "Execution Mode",
        "Lookups",
        "Total Time (s)",
        "Mean Latency (ms)",
        "P50 (ms)",
        "P95 (ms)",
        "Throughput (auth/s)",
    ]
    t8_align = ["left", "right", "right", "right", "right", "right", "right"]
    t8_seq = b8["sequential"]
    t8_conc = b8["concurrent"]
    t8_rows = [
        [
            "Sequential Lookups",
            f"{t8_seq['lookups']}",
            f"{(t8_seq['lookups']/t8_seq['throughput']):.3f} s",
            f"{t8_seq['mean']:.3f} ms",
            f"{t8_seq['p50']:.3f} ms",
            f"{t8_seq['p95']:.3f} ms",
            f"{t8_seq['throughput']:.1f} auth/s",
        ],
        [
            "Concurrent Lookups",
            f"{t8_conc['lookups']}",
            f"{t8_conc['duration']:.3f} s",
            f"{t8_conc['avg_lat']:.3f} ms",
            "-",
            "-",
            f"{t8_conc['throughput']:.1f} auth/s",
        ],
    ]
    t8_md = format_markdown_table(t8_headers, t8_rows, t8_align)

    doc = f"""# django_sockets — Performance Benchmark Report

**Generated At:** {sys_info['timestamp']}  
**Python Version:** {sys_info['python_version']}  
**Operating System:** {sys_info['os_platform']} ({sys_info['os_release']})  
**CPU Cores:** {sys_info['cpu_count']}  
**Cache Host:** {sys_info['cache_host']}:{sys_info['cache_port']}  

---

## Executive Summary

{t0_md}

---

## 1. Pub/Sub Broadcast Latency Distribution

Measures point-to-point round-trip latency from calling `async_broadcast()` through Redis pub/sub to subscriber delivery.

{t1_md}

---

## 2. Pub/Sub Burst Throughput

Measures delivery rate and latency when messages are published in rapid bursts to a single channel.

{t2_md}

---

## 3. Payload Size Scaling & Serialization Thresholds

Evaluates serialization, network transmission, and cache handling across various message sizes from 64 B to 1.5 MB.

{t3_md}

---

## 4. Channel Fan-Out Scalability (1-to-N Deliveries)

Measures broadcasting from 1 publisher to multiple subscriber WebSocket connections listening on the same channel.

{t4_md}

---

## 5. Inbound WebSocket Message Dispatch & Worker Pool Scalability

Measures incoming WebSocket message ingestion through `__ws_listener_task__` dispatching concurrently to `receive()`.

{t5_md}

---

## 6. Concurrent Publishing & Shard Contention

Measures throughput when multiple coroutines publish to the same shard simultaneously.

{t6_md}

---

## 7. End-to-End WebSocket ASGI Server (Uvicorn)

Measures real TCP loopback WebSocket communication through a running Uvicorn ASGI server.

{t7_md}

---

## 8. Authentication Middleware (DRF Token Auth)

Measures handshake token verification and user resolution performance in `DRFTokenAuthMiddleware`.

{t8_md}

---

*Report generated by `utils/benchmark.py`.*
"""

    output_path.write_text(doc)
    print(f"\n[OK] Benchmark report written successfully to: {output_path}")


# ---------------------------------------------------------------------------
# Main Runner
# ---------------------------------------------------------------------------


async def async_main(args):
    started_redis = False
    if not args.no_cache_start:
        started_redis = ensure_redis()

    print("=================================================================")
    print("        django_sockets Performance Benchmark Runner             ")
    print("=================================================================")
    print(f"Cache Host: {CACHE_HOST}:{CACHE_PORT}")
    print(f"Platform:   {platform.system()} {platform.machine()}")
    print(f"Python:     {platform.python_version()}")
    print("=================================================================\n")

    bench_data = {
        "system": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "python_version": platform.python_version(),
            "os_platform": platform.system(),
            "os_release": platform.release(),
            "cpu_count": os.cpu_count() or 1,
            "cache_host": CACHE_HOST,
            "cache_port": CACHE_PORT,
        }
    }

    try:
        # Profile 1: PubSub Latency
        bench_data["b1_pubsub_latency"] = await run_benchmark_pubsub_latency(
            samples=15 if args.quick else 30
        )

        # Profile 2: Burst Throughput
        burst_sizes = (5, 15) if args.quick else (10, 25, 50)
        bench_data["b2_pubsub_throughput"] = (
            await run_benchmark_pubsub_throughput(burst_sizes=burst_sizes)
        )

        # Profile 3: Payload Size Scaling
        bench_data["b3_payload_sizes"] = await run_benchmark_payload_sizes()

        # Profile 4: Fan-Out
        fanout_subs = (1, 5) if args.quick else (1, 5, 10, 25, 50)
        bench_data["b4_fanout"] = await run_benchmark_fanout(
            subscriber_counts=fanout_subs
        )

        # Profile 5: Inbound Dispatch
        inbound_counts = (20, 50) if args.quick else (20, 50, 100)
        bench_data["b5_inbound"] = await run_benchmark_inbound_dispatch(
            message_counts=inbound_counts
        )

        # Profile 6: Concurrent Publishing
        concurrencies = (1, 2) if args.quick else (1, 2, 4, 8)
        bench_data["b6_concurrent_publish"] = (
            await run_benchmark_concurrent_publishing(
                concurrencies=concurrencies
            )
        )

        # Profile 7: E2E Uvicorn
        bench_data["b7_e2e_uvicorn"] = await run_benchmark_e2e_uvicorn()

        # Profile 8: DRF Token Auth
        bench_data["b8_auth_middleware"] = await run_benchmark_auth_middleware(
            num_lookups=30 if args.quick else 100
        )

    finally:
        if started_redis and not args.keep_redis:
            print("\nStopping local Valkey container started for benchmark...")
            from utils.redis_stop import stop_redis

            stop_redis()

    root_dir = Path(__file__).resolve().parent.parent
    output_file = root_dir / (args.output or "benchmark.md")
    generate_markdown_report(bench_data, output_file)


def main():
    parser = argparse.ArgumentParser(
        description="Run django_sockets performance benchmarks"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="benchmark.md",
        help="Output markdown filename (default: benchmark.md)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run a quicker iteration benchmark for fast validation",
    )
    parser.add_argument(
        "--keep-redis",
        action="store_true",
        help="Do not stop the Redis container if started by the benchmark",
    )
    parser.add_argument(
        "--no-cache-start",
        action="store_true",
        help="Do not attempt to automatically start the Redis container",
    )
    args = parser.parse_args()

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
