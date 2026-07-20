import os
import django
import asyncio
import time
from django.conf import settings

# Setup Django settings dynamically to enable AnonymousUser checking
if not settings.configured:
    settings.configure(
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
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

from django_sockets.sockets import BaseSocketServer
from django_sockets.middleware.token import BaseTokenAuthMiddleware


def test_edge_cases():
    # Setup state
    state = {
        "received_data": [],
        "sent_data": [],
    }

    class TestSocketServer(BaseSocketServer):
        def receive(self, data):
            state["received_data"].append(data)

    async def send(ws_data):
        state["sent_data"].append(ws_data)

    # 1. Test BaseTokenAuthMiddleware with missing headers / query params
    class DummyAuthMiddleware(BaseTokenAuthMiddleware):
        async def get_user(self, token):
            return "UserObj"

    async def dummy_app(scope, receive, send):
        assert "user" in scope
        # Should fall back to anonymous user representation if no token is found
        assert scope["user"].is_anonymous

    # Mock scope without token
    scope_no_token = {
        "headers": [],
        "query_string": b"",
    }

    # Run auth middleware test
    auth_mw = DummyAuthMiddleware(dummy_app)
    asyncio.run(auth_mw(scope_no_token, None, None))

    # 2. Test Socket Server Edge Cases: Invalid JSON
    custom_receive = asyncio.Queue()
    custom_socket_server = TestSocketServer(
        scope={},
        receive=custom_receive.get,
        send=send,
        hosts=[
            {
                "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
            }
        ],
    )
    custom_socket_server.start_listeners()
    time.sleep(0.2)

    # A. Send connect first
    custom_receive.put_nowait({"type": "websocket.connect"})
    time.sleep(0.1)

    # B. Send invalid JSON (should not crash the server)
    custom_receive.put_nowait(
        {"type": "websocket.receive", "text": "invalid-json{"}
    )
    time.sleep(0.1)

    # C. Send valid JSON (should still be received successfully)
    custom_receive.put_nowait(
        {"type": "websocket.receive", "text": '{"valid": "data"}'}
    )
    time.sleep(0.2)

    # D. Test broadcasting to non-existent channel (should not fail)
    custom_socket_server.broadcast("non_existent_channel", {"hello": "world"})
    time.sleep(0.1)

    custom_socket_server.__kill__()

    # Assertions
    # Connection accepted message should have been sent
    assert len(state["sent_data"]) == 1
    assert state["sent_data"][0] == {"type": "websocket.accept"}

    # The valid JSON data should be processed, ignoring the invalid JSON
    assert len(state["received_data"]) == 1
    assert state["received_data"][0] == {"valid": "data"}

    print("07_edge_cases.py: PASS")


if __name__ == "__main__":
    test_edge_cases()
