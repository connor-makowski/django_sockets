import os
import django
import asyncio
import time
import socket
import threading
import uvicorn
import websockets
import json
from django.conf import settings
from django.urls import path
from django.contrib.auth import get_user_model

# Setup Django settings dynamically
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
                "NAME": ":memory:",
            }
        },
        SECRET_KEY="test-secret-key",
    )
    django.setup()

    # Build the database tables using syncdb
    from django.core.management import call_command

    call_command("migrate", run_syncdb=True, verbosity=0)

from django_sockets.sockets import BaseSocketServer
from django_sockets.utils import ProtocolTypeRouter, URLRouter
from django_sockets.middleware import DRFTokenAuthMiddleware


class IntegrationSocketServer(BaseSocketServer):
    def connect(self):
        self.channel_id = str(self.scope["user"].username)
        self.subscribe(self.channel_id)

    def receive(self, data):
        self.broadcast(self.channel_id, data)


ws_router = DRFTokenAuthMiddleware(
    URLRouter(
        [
            path("ws/", IntegrationSocketServer.as_asgi),
        ]
    )
)

application = ProtocolTypeRouter(
    {
        "websocket": ws_router,
    }
)


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _run_django_integration_test(server_type):
    # Create test user (avoid duplicate username conflict if run sequentially)
    User = get_user_model()
    username = f"testuser_{server_type}"
    user, created = User.objects.get_or_create(username=username)
    if created:
        user.set_password("password123")
        user.save()

    # Generate DRF token
    from rest_framework.authtoken.models import Token

    token, _ = Token.objects.get_or_create(user=user)
    token_key = token.key

    port = get_free_port()

    # Start the ASGI server in a background daemon thread
    def run_server():
        if server_type == "daphne":
            from daphne.server import Server
            from daphne.endpoints import build_endpoint_description_strings

            endpoints = build_endpoint_description_strings(
                host="127.0.0.1", port=port
            )
            server = Server(
                application=application,
                endpoints=endpoints,
                signal_handlers=False,
            )
            server.run()
        elif server_type == "hypercorn":
            import asyncio
            from hypercorn.config import Config
            from hypercorn.asyncio import serve

            async def main():
                config = Config()
                config.bind = [f"127.0.0.1:{port}"]
                config.loglevel = "warning"
                shutdown_event = asyncio.Event()
                await serve(
                    application, config, shutdown_trigger=shutdown_event.wait
                )

            asyncio.run(main())
        elif server_type == "uvicorn":
            uvicorn.run(
                application, host="127.0.0.1", port=port, log_level="warning"
            )
        else:
            raise ValueError(f"Unsupported server type: {server_type}")

    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(0.5)  # Wait for server to start

    async def run_test():
        # Connect using header subprotocol
        uri = f"ws://127.0.0.1:{port}/ws/"
        async with websockets.connect(
            uri, subprotocols=[f"Token.{token_key}"]
        ) as ws:
            assert ws.subprotocol == f"Token.{token_key}"

            await ws.send(json.dumps({"message": "test headers"}))
            response = await asyncio.wait_for(ws.recv(), timeout=2.0)
            assert json.loads(response) == {"message": "test headers"}

        # Connect using query parameter
        uri_qp = f"ws://127.0.0.1:{port}/ws/?token={token_key}"
        async with websockets.connect(uri_qp) as ws:
            await ws.send(json.dumps({"message": "test query params"}))
            response = await asyncio.wait_for(ws.recv(), timeout=2.0)
            assert json.loads(response) == {"message": "test query params"}

    asyncio.run(run_test())


def test_django_integration_uvicorn():
    _run_django_integration_test("uvicorn")


def test_django_integration_daphne():
    _run_django_integration_test("daphne")


def test_django_integration_hypercorn():
    _run_django_integration_test("hypercorn")


if __name__ == "__main__":
    test_django_integration_uvicorn()
    print("06_django_integration.py (Uvicorn): PASS")
    test_django_integration_daphne()
    print("06_django_integration.py (Daphne): PASS")
    test_django_integration_hypercorn()
    print("06_django_integration.py (Hypercorn): PASS")
