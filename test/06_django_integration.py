import os
import django
import asyncio
import time
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
            "daphne",
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

from channels.testing import WebsocketCommunicator
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


def test_django_integration():
    # Create test user
    User = get_user_model()
    user = User.objects.create_user(username="testuser", password="password123")

    # Generate DRF token
    from rest_framework.authtoken.models import Token

    token = Token.objects.create(user=user)
    token_key = token.key

    async def run_test():
        # Connect using header subprotocol
        communicator = WebsocketCommunicator(
            application,
            "ws/",
            headers=[
                (b"sec-websocket-protocol", f"Token.{token_key}".encode())
            ],
        )
        connected, subprotocol = await communicator.connect()
        assert connected
        assert subprotocol == f"Token.{token_key}"

        await communicator.send_json_to({"message": "test headers"})
        response = await communicator.receive_json_from()
        assert response == {"message": "test headers"}
        await communicator.disconnect()

        # Connect using query parameter
        communicator_qp = WebsocketCommunicator(
            application, f"ws/?token={token_key}"
        )
        connected_qp, _ = await communicator_qp.connect()
        assert connected_qp

        await communicator_qp.send_json_to({"message": "test query params"})
        response_qp = await communicator_qp.receive_json_from()
        assert response_qp == {"message": "test query params"}
        await communicator_qp.disconnect()

    asyncio.run(run_test())
    print("06_django_integration.py: PASS")


if __name__ == "__main__":
    test_django_integration()
