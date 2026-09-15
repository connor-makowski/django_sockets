# django_sockets — Performance Benchmark Report

**Generated At:** 2026-09-15 19:12:45 UTC  
**Python Version:** 3.12.3  
**Operating System:** Linux (7.0.0-31-generic)  
**CPU Cores:** 64  
**Cache Host:** localhost:6379  

---

## Executive Summary

| Benchmark Profile              | Key Metric          | Measured Value |
| :----------------------------- | :------------------ | -------------: |
| Pub/Sub Message Latency        | P50 Latency         |        0.16 ms |
| Pub/Sub Burst Streaming        | Peak Throughput     |   5685.7 msg/s |
| 1.5MB Payload (>1MB)           | Bandwidth           |    375.86 MB/s |
| Fan-Out (50 Subscribers)       | Delivered Rate      |  11376.6 msg/s |
| Inbound WS Dispatch            | Peak Throughput     |   8960.4 msg/s |
| Concurrent Publishing          | Peak Throughput     |   9219.0 msg/s |
| End-to-End WebSocket (Uvicorn) | Mean Round-Trip     |        0.67 ms |
| DRF Token Authentication       | Handshake Auth Rate |  2318.2 auth/s |

---

## 1. Pub/Sub Broadcast Latency Distribution

Measures point-to-point round-trip latency from calling `async_broadcast()` through Redis pub/sub to subscriber delivery.

| Metric            | Pub/Sub Latency (ms) |
| :---------------- | -------------------: |
| Samples Collected |                   30 |
| Min Latency       |              0.15 ms |
| Mean Latency      |              0.23 ms |
| Median (P50)      |              0.16 ms |
| P90 Latency       |              0.22 ms |
| P95 Latency       |              0.23 ms |
| P99 Latency       |              2.11 ms |
| Max Latency       |              2.11 ms |
| Std Deviation     |              0.36 ms |

---

## 2. Pub/Sub Burst Throughput

Measures delivery rate and latency when messages are published in rapid bursts to a single channel.

| Burst Batch Size | Delivered Messages | Total Duration (s) | Throughput (msg/s) | Mean Latency (ms) | Median Latency (ms) |
| ---------------: | -----------------: | -----------------: | -----------------: | ----------------: | ------------------: |
|               10 |                 10 |            0.003 s |       3543.2 msg/s |           0.37 ms |             0.21 ms |
|               25 |                 25 |            0.005 s |       4863.3 msg/s |           0.32 ms |             0.27 ms |
|               50 |                 50 |            0.009 s |       5685.7 msg/s |           0.28 ms |             0.21 ms |

---

## 3. Payload Size Scaling & Serialization Thresholds

Evaluates serialization, network transmission, and cache handling across various message sizes from 64 B to 1.5 MB.

| Payload Description        |     Bytes | Samples | Min (ms) | Mean (ms) | P50 (ms) | P95 (ms) | Max (ms) | Bandwidth (MB/s) |
| :------------------------- | --------: | ------: | -------: | --------: | -------: | -------: | -------: | ---------------: |
| 64 B (Tiny / Ping)         |        64 |      10 |     0.18 |      0.34 |     0.19 |     1.73 |     1.73 |             0.18 |
| 1 KB (Small Event)         |     1,024 |      10 |     0.18 |      0.19 |     0.19 |     0.21 |     0.21 |             5.13 |
| 64 KB (Medium State)       |    65,536 |      10 |     0.38 |      0.50 |     0.44 |     0.76 |     0.76 |           123.92 |
| 512 KB (Large Dataset)     |   524,288 |       5 |     1.85 |      2.67 |     2.32 |     4.13 |     4.13 |           187.46 |
| 1.5 MB (>1MB Cache Bypass) | 1,572,864 |       3 |     2.82 |      3.99 |     3.28 |     5.87 |     5.87 |           375.86 |

---

## 4. Channel Fan-Out Scalability (1-to-N Deliveries)

Measures broadcasting from 1 publisher to multiple subscriber WebSocket connections listening on the same channel.

| Subscribers | Broadcasts Sent | Messages Delivered | Total Time (s) | Broadcast Rate (pub/s) | Fan-Out Delivery Rate (msg/s) | Mean Delivery Latency (ms) |
| ----------: | --------------: | -----------------: | -------------: | ---------------------: | ----------------------------: | -------------------------: |
|           1 |               5 |                  5 |        0.012 s |            400.8 pub/s |                   400.8 msg/s |                    0.57 ms |
|           5 |               5 |                 25 |        0.013 s |            384.2 pub/s |                  1921.2 msg/s |                    0.75 ms |
|          10 |               5 |                 50 |        0.014 s |            353.7 pub/s |                  3536.9 msg/s |                    1.07 ms |
|          25 |               5 |                125 |        0.016 s |            312.9 pub/s |                  7823.6 msg/s |                    1.80 ms |
|          50 |               5 |                250 |        0.022 s |            227.5 pub/s |                 11376.6 msg/s |                    3.80 ms |

---

## 5. Inbound WebSocket Message Dispatch & Worker Pool Scalability

Measures incoming WebSocket message ingestion through `__ws_listener_task__` dispatching concurrently to `receive()`.

| Incoming Messages | Processed | Worker Pool Threads | Max Concurrent Threads | Total Time (ms) | Throughput (msg/s) |
| ----------------: | --------: | ------------------: | ---------------------: | --------------: | -----------------: |
|                20 |        20 |                  16 |                     19 |         5.50 ms |       3635.5 msg/s |
|                50 |        50 |                  31 |                     33 |         6.41 ms |       7800.3 msg/s |
|               100 |       100 |                  31 |                     33 |        11.16 ms |       8960.4 msg/s |

---

## 6. Concurrent Publishing & Shard Contention

Measures throughput when multiple coroutines publish to the same shard simultaneously.

| Concurrency Level | Total Messages | Total Time (s) | Throughput (msg/s) | Avg Latency per Task (ms) |
| ----------------: | -------------: | -------------: | -----------------: | ------------------------: |
|       1 worker(s) |             50 |        0.007 s |       7145.2 msg/s |                   0.14 ms |
|       2 worker(s) |            100 |        0.012 s |       8408.5 msg/s |                   0.24 ms |
|       4 worker(s) |            200 |        0.022 s |       9219.0 msg/s |                   0.43 ms |
|       8 worker(s) |            400 |        0.045 s |       8897.0 msg/s |                   0.90 ms |

---

## 7. End-to-End WebSocket ASGI Server (Uvicorn)

Measures real TCP loopback WebSocket communication through a running Uvicorn ASGI server.

| Interaction Profile  |   Count | Min (ms) | Mean (ms) | P50 (ms) | P95 (ms) | Max (ms) |   Throughput |
| :------------------- | ------: | -------: | --------: | -------: | -------: | -------: | -----------: |
| Sequential Ping-Pong | 20 reqs |     0.47 |      0.67 |     0.64 |     0.94 |     0.94 | 1484.4 req/s |
| Burst Stream         | 25 msgs |        - |         - |        - |        - |  6.72 ms | 3722.7 msg/s |

---

## 8. Authentication Middleware (DRF Token Auth)

Measures handshake token verification and user resolution performance in `DRFTokenAuthMiddleware`.

| Execution Mode     | Lookups | Total Time (s) | Mean Latency (ms) | P50 (ms) | P95 (ms) | Throughput (auth/s) |
| :----------------- | ------: | -------------: | ----------------: | -------: | -------: | ------------------: |
| Sequential Lookups |     100 |        0.043 s |          0.431 ms | 0.423 ms | 0.516 ms |       2318.2 auth/s |
| Concurrent Lookups |     100 |        0.047 s |          0.465 ms |        - |        - |       2149.5 auth/s |

---

*Report generated by `utils/benchmark.py`.*
