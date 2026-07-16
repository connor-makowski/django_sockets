---
name: add-test
description: Add or extend a test for django_sockets. Use when asked to write a test, add test coverage, or verify new django_sockets behavior.
---

# Adding a Test

Tests use `pytest`, run via `nox` across Python 3.11–3.14. `testpaths = ["test"]` and `python_files = ["*.py"]` are configured in `pyproject.toml`, so every `.py` file under `test/` is collected by pytest.

**Convention**: Test files are named with a zero-padded two-digit number followed by a description, e.g., `06_new_feature.py`. If adding a new test, choose the next available number.

**Pattern:**

```python
from django_sockets.sockets import BaseSocketServer
import asyncio, time, os

PASS = False

# Override the send method to update the PASS variable if a subscribed broadcast is received and sent
async def send(ws_data):
    global PASS
    if ws_data == "expected message":
        PASS = True

# Test the socket server cache process
base_receive = asyncio.Queue()
base_socket_server = BaseSocketServer(
    scope={},
    receive=base_receive.get,
    send=send,
    hosts=[
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ],
)
base_socket_server.start_listeners()
base_socket_server.subscribe("my_channel")
base_socket_server.broadcast("my_channel", "expected message")

# Give the async functions a small amount of time to complete
time.sleep(0.2)

if PASS:
    print("06_new_feature.py: PASS")
else:
    print("06_new_feature.py: FAIL")
```

After adding a test, run it with the [test](../test/SKILL.md) skill.
