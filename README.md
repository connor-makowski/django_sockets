# Django Sockets

[![PyPI version](https://badge.fury.io/py/django_sockets.svg)](https://badge.fury.io/py/django_sockets)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Simplified Django WebSocket integrations designed for speed, flexibility, and cloud-cache scaling (Valkey/Redis). Works seamlessly on single, distributed, or serverless cache setups.

- **ASGI Server Compatibility**: Compatible with **any standard ASGI server** (such as Uvicorn, Daphne, or Hypercorn).
- **Multi-Framework**: Can also be used in **non-Django applications** (Flask, FastAPI, or raw Python) for lightweight Pub/Sub messaging.

---

## Key Features

- **Cache-Backed Pub/Sub**: Async broadcasting using Redis or Valkey.
- **Simplified Middleware**: Simple authentication wrappers for Django Sessions and Django Rest Framework (DRF) Tokens.
- **ASGI Native**: Implements standard `ProtocolTypeRouter` and `URLRouter` for minimal overhead.
- **Subprotocol Auth**: Supports secure token-based authentication via the `Sec-WebSocket-Protocol` header.
- **Minimal Boilerplate**: Define a class with `connect`, `receive`, and `disconnect` hooks and you're ready to go.

---

## Installation & Setup

```bash
pip install django_sockets
```

### Valkey/Redis Setup
To use broadcasting and pub/sub features, you need a Redis or Valkey cache server:
```bash
# Start a local Valkey cache via Docker
docker run -d -p 6379:6379 --name django_sockets_cache valkey/valkey:7
```

---

## Quickstart (Django)

### 1. Define your Socket Server
Create a `ws.py` in your Django app:

```python
from django.urls import path
from django_sockets.sockets import BaseSocketServer
from django_sockets.middleware import SessionAuthMiddleware
from django_sockets.utils import URLRouter


class MyCounterSocket(BaseSocketServer):
    def configure(self):
        # Configure cache hosts (optional, needed for pub/sub)
        self.hosts = [{"address": "redis://localhost:6379"}]

    def connect(self):
        # Scope-aware user extraction
        self.channel_id = f"user_{self.scope['user'].id}"
        self.subscribe(self.channel_id)

    def receive(self, data):
        # Broadcast incoming JSON to all subscribers of this channel
        self.broadcast(self.channel_id, data)


# Wrap with authentication middleware and URL routing
websocket_application = SessionAuthMiddleware(
    URLRouter(
        [
            path("ws/counter/", MyCounterSocket.as_asgi),
        ]
    )
)
```

### 2. Configure ASGI Entrypoint
In your Django `asgi.py` (ensure imports are ordered correctly to allow proper Django initialization):

```python
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myapp.settings")
django_asgi_app = get_asgi_application()

# Import django_sockets after Django initialization
from django_sockets.utils import ProtocolTypeRouter
from .ws import websocket_application

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": websocket_application,
    }
)
```

---

## Running the ASGI Server

You can run your Django ASGI application using any ASGI-compliant web server:

### Uvicorn
```bash
pip install uvicorn
uvicorn myapp.asgi:application --reload
```

### Daphne
```bash
pip install daphne
daphne -p 8000 myapp.asgi:application
```

### Hypercorn
```bash
pip install hypercorn
hypercorn myapp.asgi:application --bind 127.0.0.1:8000
```

---

## Guides & Examples

We provide detailed step-by-step tutorials and code samples:

- **[Step-by-Step Django Tutorial (TUTORIAL.md)](TUTORIAL.md)**: Build a fully-featured, user-scoped real-time counter using session or DRF token authentication from scratch.
- **[Examples Directory](examples/)**:
  - `examples/django/myapp`: Full project showing standard Django Session authentication.
  - `examples/django/myapp_drf`: Full project showing DRF Token authentication.
  - `examples/without_django`: Standalone python pub/sub without Django dependencies.

---

## Non-Django Usage (Flask, FastAPI, Raw Python)

`django_sockets` can run without Django's registry:

### 1. Broadcaster (Sending from Flask/FastAPI)
Publish events from any HTTP route to WebSocket clients:
```python
from flask import Flask, request
from django_sockets.broadcaster import Broadcaster

app = Flask(__name__)
broadcaster = Broadcaster(hosts=[{"address": "redis://localhost:6379"}])


@app.route("/alert", methods=["POST"])
def send_alert():
    broadcaster.broadcast("alerts_channel", request.json)
    return {"status": "Alert sent"}
```

### 2. Running a Pure ASGI Server
Initialize `BaseSocketServer` manually in custom ASGI configurations or raw Python scripts:
```python
import asyncio
from django_sockets.sockets import BaseSocketServer


async def my_send_handler(data):
    print("Sent:", data)


receive_queue = asyncio.Queue()
socket_server = BaseSocketServer(
    scope={},
    receive=receive_queue.get,
    send=my_send_handler,
    hosts=[{"address": "redis://localhost:6379"}],
)
socket_server.start_listeners()
```

---

## Development & Testing

Run the full pytest suite:
```bash
uv run pytest
```

For manual testing, manage the local Docker Valkey instance using:
```bash
uv run python utils/redis_start.py
# Run your manual scripts (e.g. uv run test/06_django_integration.py)
uv run python utils/redis_stop.py
```

---

## Attributions

Some of the code in this repository is formed similarly to or inspired by `channels_redis` and `django_channels`. Many thanks to their authors for the original work and inspiration.