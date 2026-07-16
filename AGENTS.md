# django_sockets — Developer Guide

## Project Purpose

`django_sockets` is a library providing simplified Django websocket processes designed to work with cloud caches (valkey/redis on single, distributed, or serverless setups). It simplifies async WebSocket connections, routing, middleware, and pub/sub broadcasting using Daphne and Django.

---

> **IMPORTANT — DO NOT RUN A RELEASE CYCLE.** Do not bump versions, generate docs, build distributions, or publish to PyPI. Release steps are owner-only. If you think a release is needed, flag it and stop.

---

## Directory Layout (relevant files only)

```
django_sockets/
  __init__.py        # Package exports + README as docstring (overwritten by utils/docs.py)
  broadcaster.py     # Broadcast endpoint management
  pubsub.py          # Pub/sub connection and loop logic for valkey/redis
  sockets.py         # Core: BaseSocketServer class for handling websocket connections
  utils.py           # Routing utilities (ProtocolTypeRouter, URLRouter, etc.)
  middleware/        # Auth middlewares (SessionAuthMiddleware, DRFTokenAuthMiddleware, etc.)
test/
  01_basic_function.py
  02_basic_function_big.py
  03_custom_socket_connection.py
  04_custom_socket_receive.py
  05_socket_lifecycle.py
  06_django_integration.py
  07_edge_cases.py
  08_failure_modes.py
  conftest.py
utils/
  docs.py            # Generate pdoc HTML docs — DO NOT RUN (release only)
  prettify.py        # Format/lint code with autoflake + black
  test.py            # Run tests (runs inside Docker container)
Dockerfile           # Testing/linting container definition
noxfile.py           # Nox configuration for running pytest across multiple Python versions
pyproject.toml       # Project metadata, black/pytest config, and dependencies
setup.cfg            # Setup metadata and package options
publish.sh           # PyPI publishing script — DO NOT RUN
```

---

## Skills

| Skill | Use when |
|---|---|
| [test](.claude/skills/test/SKILL.md) | Running the test suite via `nox` or `pytest` (`uv run nox` or `uv run pytest`) |
| [add-test](.claude/skills/add-test/SKILL.md) | Adding or extending a test script under `test/` |
| [lint](.claude/skills/lint/SKILL.md) | Formatting code with autoflake + black |
| [release](.claude/skills/release/SKILL.md) | Owner-only — explains why to stop and flag instead of executing a release |

---

## Core Architecture

### Key Files

**`django_sockets/sockets.py`** — the core class:
- `BaseSocketServer` — The ASGI application wrapper for handling websockets. It manages client connection (`connect()`), message receiving (`receive(data)`), broadcasting (`broadcast(channel_id, data)`), subscription (`subscribe(channel_id)`), and disconnects (`disconnect()`).

**`django_sockets/pubsub.py`** — pub/sub management:
- `PubSub` — Connects to valkey/redis cache backends and runs the asynchronous pub/sub listener loop, sending updates back to the relevant sockets.

**`django_sockets/middleware/`** — auth & scope middlewares:
- `SessionAuthMiddleware`: Extracts the user from the Django session.
- `DRFTokenAuthMiddleware`: Extracts the user from a Django Rest Framework Token, supporting query parameters (`?token=...`) and websocket protocols (`sec-websocket-protocol` header in format `Token.<token>`).

**`django_sockets/utils.py`** — ASGI routing:
- `ProtocolTypeRouter`: Routes connections based on their protocol (e.g. `"http"` vs `"websocket"`).
- `URLRouter`: Maps url paths to ASGI/Socket applications.

### Configuration / Setup

Websocket server classes extend `BaseSocketServer` and define their hooks:
```python
class SocketServer(BaseSocketServer):
    def configure(self):
        # Set redis/valkey hosts (list of host dicts)
        self.hosts = [{"address": "redis://localhost:6379"}]

    def connect(self):
        self.channel_id = str(self.scope['user'].id)
        self.subscribe(self.channel_id)

    def receive(self, data):
        # Handle parsed json dictionary data
        self.broadcast(self.channel_id, data)
```

---

## Coding Conventions

- **Line length**: 80 characters (black config in `pyproject.toml`)
- **Python version**: >= 3.10
- **Environment Management**: Use `uv`. Run `uv sync --extra dev` after modifying dependencies.
- **Documentation**: The primary documentation is `README.md`. `django_sockets/__init__.py` has its docstring generated dynamically from `README.md` during the release process (by `utils/docs.py`). **Do not edit the docstring in `__init__.py` directly.**
- **Code style**: Use `uv run utils/prettify.py` to clean and format Python code.

---

Python: **≥ 3.10** | Core Cache: Valkey / Redis
