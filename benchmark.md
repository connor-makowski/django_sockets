# django_sockets — Performance Benchmark Report

**Generated At:** 2026-09-17 17:37:13 UTC  
**Python Version:** 3.12.3  
**Operating System:** Linux (7.0.0-31-generic)  
**CPU Cores:** 64  
**Cache Host:** localhost:6379  

---

## Executive Summary

| Benchmark Profile              | Key Metric          | Measured Value |
| :----------------------------- | :------------------ | -------------: |
| Pub/Sub Message Latency        | P50 Latency         |        0.16 ms |
| Pub/Sub Burst Streaming        | Peak Throughput     |   5973.9 msg/s |
| 1.5MB Payload (>1MB)           | Bandwidth           |    354.08 MB/s |
| Fan-Out (50 Subscribers)       | Delivered Rate      |  11843.9 msg/s |
| Inbound WS Dispatch            | Peak Throughput     |   8732.6 msg/s |
| Concurrent Publishing          | Peak Throughput     |   9902.1 msg/s |
| End-to-End WebSocket (Uvicorn) | Mean Round-Trip     |        0.66 ms |
| DRF Token Authentication       | Handshake Auth Rate |  2147.2 auth/s |

---

## 1. Pub/Sub Broadcast Latency Distribution

Measures point-to-point round-trip latency from calling `async_broadcast()` through Redis pub/sub to subscriber delivery.

| Metric            | Pub/Sub Latency (ms) |
| :---------------- | -------------------: |
| Samples Collected |                   30 |
| Min Latency       |              0.14 ms |
| Mean Latency      |              0.23 ms |
| Median (P50)      |              0.16 ms |
| P90 Latency       |              0.21 ms |
| P95 Latency       |              0.25 ms |
| P99 Latency       |              2.11 ms |
| Max Latency       |              2.11 ms |
| Std Deviation     |              0.36 ms |

---

## 2. Pub/Sub Burst Throughput

Measures delivery rate and latency when messages are published in rapid bursts to a single channel.

| Burst Batch Size | Delivered Messages | Total Duration (s) | Throughput (msg/s) | Mean Latency (ms) | Median Latency (ms) |
| ---------------: | -----------------: | -----------------: | -----------------: | ----------------: | ------------------: |
|               10 |                 10 |            0.003 s |       3353.6 msg/s |           0.39 ms |             0.21 ms |
|               25 |                 25 |            0.005 s |       4939.7 msg/s |           0.29 ms |             0.21 ms |
|               50 |                 50 |            0.008 s |       5973.9 msg/s |           0.26 ms |             0.22 ms |

---

## 3. Payload Size Scaling & Serialization Thresholds

Evaluates serialization, network transmission, and cache handling across various message sizes from 64 B to 1.5 MB.

| Payload Description        |     Bytes | Samples | Min (ms) | Mean (ms) | P50 (ms) | P95 (ms) | Max (ms) | Bandwidth (MB/s) |
| :------------------------- | --------: | ------: | -------: | --------: | -------: | -------: | -------: | ---------------: |
| 64 B (Tiny / Ping)         |        64 |      10 |     0.16 |      0.30 |     0.17 |     1.51 |     1.51 |             0.20 |
| 1 KB (Small Event)         |     1,024 |      10 |     0.17 |      0.18 |     0.18 |     0.20 |     0.20 |             5.40 |
| 64 KB (Medium State)       |    65,536 |      10 |     0.36 |      0.48 |     0.38 |     0.89 |     0.89 |           129.90 |
| 512 KB (Large Dataset)     |   524,288 |       5 |     1.78 |      2.53 |     2.02 |     4.19 |     4.19 |           197.87 |
| 1.5 MB (>1MB Cache Bypass) | 1,572,864 |       3 |     3.39 |      4.24 |     3.54 |     5.79 |     5.79 |           354.08 |

---

## 4. Channel Fan-Out Scalability (1-to-N Deliveries)

Measures broadcasting from 1 publisher to multiple subscriber WebSocket connections listening on the same channel.

| Subscribers | Broadcasts Sent | Messages Delivered | Total Time (s) | Broadcast Rate (pub/s) | Fan-Out Delivery Rate (msg/s) | Mean Delivery Latency (ms) |
| ----------: | --------------: | -----------------: | -------------: | ---------------------: | ----------------------------: | -------------------------: |
|           1 |               5 |                  5 |        0.013 s |            396.4 pub/s |                   396.4 msg/s |                    0.60 ms |
|           5 |               5 |                 25 |        0.013 s |            378.4 pub/s |                  1891.9 msg/s |                    0.80 ms |
|          10 |               5 |                 50 |        0.014 s |            356.4 pub/s |                  3563.8 msg/s |                    1.00 ms |
|          25 |               5 |                125 |        0.017 s |            298.3 pub/s |                  7457.2 msg/s |                    2.12 ms |
|          50 |               5 |                250 |        0.021 s |            236.9 pub/s |                 11843.9 msg/s |                    3.41 ms |

---

## 5. Inbound WebSocket Message Dispatch & Worker Pool Scalability

Measures incoming WebSocket message ingestion through `__ws_listener_task__` dispatching concurrently to `receive()`.

| Incoming Messages | Processed | Worker Pool Threads | Max Concurrent Threads | Total Time (ms) | Throughput (msg/s) |
| ----------------: | --------: | ------------------: | ---------------------: | --------------: | -----------------: |
|                20 |        20 |                  16 |                     18 |         5.54 ms |       3608.9 msg/s |
|                50 |        50 |                  31 |                     33 |         6.34 ms |       7881.5 msg/s |
|               100 |       100 |                  31 |                     33 |        11.45 ms |       8732.6 msg/s |

---

## 6. Concurrent Publishing & Shard Contention

Measures throughput when multiple coroutines publish to the same shard simultaneously.

| Concurrency Level | Total Messages | Total Time (s) | Throughput (msg/s) | Avg Latency per Task (ms) |
| ----------------: | -------------: | -------------: | -----------------: | ------------------------: |
|       1 worker(s) |             50 |        0.007 s |       7450.8 msg/s |                   0.13 ms |
|       2 worker(s) |            100 |        0.010 s |       9902.1 msg/s |                   0.20 ms |
|       4 worker(s) |            200 |        0.024 s |       8335.2 msg/s |                   0.48 ms |
|       8 worker(s) |            400 |        0.041 s |       9797.6 msg/s |                   0.82 ms |

---

## 7. End-to-End WebSocket ASGI Server (Uvicorn)

Measures real TCP loopback WebSocket communication through a running Uvicorn ASGI server.

| Interaction Profile  |   Count | Min (ms) | Mean (ms) | P50 (ms) | P95 (ms) | Max (ms) |   Throughput |
| :------------------- | ------: | -------: | --------: | -------: | -------: | -------: | -----------: |
| Sequential Ping-Pong | 20 reqs |     0.50 |      0.66 |     0.63 |     0.89 |     0.89 | 1519.8 req/s |
| Burst Stream         | 25 msgs |        - |         - |        - |        - |  6.54 ms | 3822.1 msg/s |

---

## 8. Authentication Middleware (DRF Token Auth)

Measures handshake token verification and user resolution performance in `DRFTokenAuthMiddleware`.

| Execution Mode     | Lookups | Total Time (s) | Mean Latency (ms) | P50 (ms) | P95 (ms) | Throughput (auth/s) |
| :----------------- | ------: | -------------: | ----------------: | -------: | -------: | ------------------: |
| Sequential Lookups |     100 |        0.047 s |          0.466 ms | 0.454 ms | 0.545 ms |       2147.2 auth/s |
| Concurrent Lookups |     100 |        0.048 s |          0.483 ms |        - |        - |       2069.7 auth/s |

---

*Report generated by `utils/benchmark.py`.*
