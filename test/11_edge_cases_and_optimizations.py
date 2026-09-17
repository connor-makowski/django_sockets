from django_sockets.sockets import BaseSocketServer
from django_sockets.middleware import (
    DRFTokenAuthMiddleware,
    SessionAuthMiddleware,
)
from django.contrib.auth.models import AnonymousUser
import asyncio, time, os, json


def test_server_initiated_close():
    received_messages = []

    async def send(ws_data):
        received_messages.append(ws_data)

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]

    class CloseSocketServer(BaseSocketServer):
        def connect(self):
            # Server immediately closes connection with custom code 4001
            self.close(code=4001)

    server = CloseSocketServer(scope={}, receive=q.get, send=send, hosts=hosts)
    server.start_listeners()
    time.sleep(0.1)

    q.put_nowait({"type": "websocket.connect"})
    time.sleep(0.2)

    assert any(
        msg.get("type") == "websocket.close" and msg.get("code") == 4001
        for msg in received_messages
    )
    assert server.is_alive is False
    print("11_edge_cases_and_optimizations.py (server_close): PASS")


def test_disconnect_signature_compatibility():
    state = {"disconnected": False}

    class CustomNoArgDisconnectServer(BaseSocketServer):
        def disconnect(self):
            # Signature without `code` positional parameter
            state["disconnected"] = True

    async def send(ws_data):
        pass

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]
    server = CustomNoArgDisconnectServer(
        scope={}, receive=q.get, send=send, hosts=hosts
    )
    server.start_listeners()
    time.sleep(0.1)

    # Trigger disconnect
    q.put_nowait({"type": "websocket.disconnect", "code": 1001})
    time.sleep(0.2)

    assert state["disconnected"] is True
    print("11_edge_cases_and_optimizations.py (disconnect_sig): PASS")


def test_async_disconnect_signature_compatibility():
    state = {"disconnected": False}

    class CustomNoArgAsyncDisconnectServer(BaseSocketServer):
        async def disconnect(self):
            # Async signature without `code` positional parameter
            await asyncio.sleep(0.01)
            state["disconnected"] = True

    async def send(ws_data):
        pass

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]
    server = CustomNoArgAsyncDisconnectServer(
        scope={}, receive=q.get, send=send, hosts=hosts
    )
    server.start_listeners()
    time.sleep(0.1)

    # Trigger disconnect
    q.put_nowait({"type": "websocket.disconnect", "code": 1001})
    time.sleep(0.2)

    assert state["disconnected"] is True
    print("11_edge_cases_and_optimizations.py (async_disconnect_sig): PASS")


def test_query_param_token_auth():
    class DummyDRFTokenAuth(DRFTokenAuthMiddleware):
        async def get_user(self, token):
            if token == "secret-token-123":
                return {"username": "authenticated_user"}
            return None

    captured = {}

    async def dummy_app(scope, receive, send):
        captured["scope"] = scope

    middleware = DummyDRFTokenAuth(dummy_app)

    async def run_auth_test():
        # Test ?token=...
        scope_query = {
            "type": "websocket",
            "headers": [],
            "query_string": b"token=secret-token-123",
        }
        await middleware(scope_query, None, None)
        assert captured["scope"]["user"] == {"username": "authenticated_user"}

        # Test ?auth_token=...
        scope_auth_query = {
            "type": "websocket",
            "headers": [],
            "query_string": b"auth_token=secret-token-123",
        }
        await middleware(scope_auth_query, None, None)
        assert captured["scope"]["user"] == {"username": "authenticated_user"}

        # Test invalid token
        scope_invalid = {
            "type": "websocket",
            "headers": [],
            "query_string": b"token=invalid-token",
        }
        await middleware(scope_invalid, None, None)
        assert isinstance(captured["scope"]["user"], AnonymousUser)

    asyncio.run(run_auth_test())
    print("11_edge_cases_and_optimizations.py (query_param_auth): PASS")


def test_url_router_trailing_slash_flexibility():
    from django_sockets.utils import URLRouter
    from django.urls import path

    called_scopes = []

    async def sample_app(scope, receive, send):
        called_scopes.append(scope)

    router = URLRouter([path("ws/", sample_app)])

    async def run_router_tests():
        # Match with trailing slash: /ws/
        await router({"type": "websocket", "path": "/ws/"}, None, None)
        assert len(called_scopes) == 1

        # Match without trailing slash: /ws
        await router({"type": "websocket", "path": "/ws"}, None, None)
        assert len(called_scopes) == 2

    asyncio.run(run_router_tests())
    print("11_edge_cases_and_optimizations.py (url_router_slash): PASS")


def test_multi_cookie_header_session_auth():
    class DummySessionAuth(SessionAuthMiddleware):
        async def get_user_from_session_key(self, session_key):
            if session_key == "valid-sess-456":
                return {"username": "session_user"}
            return None

    captured = {}

    async def dummy_app(scope, receive, send):
        captured["scope"] = scope

    middleware = DummySessionAuth(dummy_app)

    async def run_cookie_test():
        # Multiple cookie headers in scope (as supported in ASGI / HTTP2)
        scope = {
            "type": "websocket",
            "headers": [
                (b"user-agent", b"pytest"),
                (b"cookie", b"other_cookie=123"),
                (b"cookie", b"sessionid=valid-sess-456; theme=dark"),
            ],
        }
        await middleware(scope, None, None)
        assert captured["scope"]["user"] == {"username": "session_user"}

    asyncio.run(run_cookie_test())
    print("11_edge_cases_and_optimizations.py (multi_cookie): PASS")


def test_non_string_channel_identifiers():
    import uuid

    received = []

    async def send(ws_data):
        received.append(ws_data)

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]

    server = BaseSocketServer(scope={}, receive=q.get, send=send, hosts=hosts)
    server.start_listeners()

    # Subscribe using integer channel ID and UUID channel ID
    int_channel = 98765
    uuid_channel = uuid.uuid4()

    server.subscribe(int_channel)
    server.subscribe(uuid_channel)
    time.sleep(0.2)

    server.broadcast(int_channel, {"data": "int_chan"})
    server.broadcast(uuid_channel, {"data": "uuid_chan"})
    time.sleep(0.3)

    server.__kill__()

    assert len(received) == 2
    decoded = [json.loads(r["text"]) for r in received]
    assert {"data": "int_chan"} in decoded
    assert {"data": "uuid_chan"} in decoded
    print("11_edge_cases_and_optimizations.py (non_string_channels): PASS")


def test_large_payload_multi_broadcast():
    received_1 = []
    received_2 = []

    async def send1(ws_data):
        received_1.append(ws_data)

    async def send2(ws_data):
        received_2.append(ws_data)

    q1 = asyncio.Queue()
    q2 = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]

    s1 = BaseSocketServer(scope={}, receive=q1.get, send=send1, hosts=hosts)
    s2 = BaseSocketServer(scope={}, receive=q2.get, send=send2, hosts=hosts)
    s1.start_listeners()
    s2.start_listeners()

    s1.subscribe("big_multi_1")
    s2.subscribe("big_multi_2")
    time.sleep(0.2)

    # Large >1MB payload broadcast to multiple channels simultaneously
    big_payload = {f"k_{i}": f"v_{i}" for i in range(1024 * 256)}
    s1.broadcast(["big_multi_1", "big_multi_2"], big_payload)
    time.sleep(1.0)

    s1.__kill__()
    s2.__kill__()

    assert len(received_1) == 1
    assert len(received_2) == 1
    assert json.loads(received_1[0]["text"]) == big_payload
    assert json.loads(received_2[0]["text"]) == big_payload
    print("11_edge_cases_and_optimizations.py (large_multi_broadcast): PASS")


def test_custom_subprotocol_negotiation():
    received = []

    async def send(ws_data):
        received.append(ws_data)

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]

    class SubprotocolSocketServer(BaseSocketServer):
        def configure(self):
            self.subprotocol = "graphql-transport-ws"

    server = SubprotocolSocketServer(
        scope={}, receive=q.get, send=send, hosts=hosts
    )
    server.start_listeners()
    time.sleep(0.1)

    q.put_nowait({"type": "websocket.connect"})
    time.sleep(0.2)

    server.__kill__()

    assert any(
        msg.get("type") == "websocket.accept"
        and msg.get("subprotocol") == "graphql-transport-ws"
        for msg in received
    )
    print("11_edge_cases_and_optimizations.py (subprotocol_negotiation): PASS")


def test_init_ws_decoder_and_subprotocol():
    received = []
    received_payloads = []

    async def send(ws_data):
        received.append(ws_data)

    class CustomDecodeServer(BaseSocketServer):
        def receive(self, data):
            received_payloads.append(data)

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]

    server = CustomDecodeServer(
        scope={},
        receive=q.get,
        send=send,
        hosts=hosts,
        ws_decoder=lambda text: f"CUSTOM_DECODED:{text}",
        subprotocol="wamp.2.json",
    )
    server.start_listeners()
    time.sleep(0.1)

    q.put_nowait({"type": "websocket.connect"})
    time.sleep(0.1)

    q.put_nowait({"type": "websocket.receive", "text": "hello-world"})
    time.sleep(0.1)

    server.__kill__()

    assert any(
        msg.get("type") == "websocket.accept"
        and msg.get("subprotocol") == "wamp.2.json"
        for msg in received
    )
    assert received_payloads == ["CUSTOM_DECODED:hello-world"]
    print("11_edge_cases_and_optimizations.py (init_decoder_subprotocol): PASS")


def test_cluster_config_initialization():
    from django_sockets.pubsub import ShardConnection, PubSubLayer

    layer = PubSubLayer(
        hosts=[{"address": "redis://127.0.0.1:6379", "cluster": True}]
    )
    shard = layer.shards[0]
    assert shard.is_cluster is True
    assert shard.connection_pool is None
    print("11_edge_cases_and_optimizations.py (cluster_init): PASS")


if __name__ == "__main__":
    test_server_initiated_close()
    test_disconnect_signature_compatibility()
    test_async_disconnect_signature_compatibility()
    test_query_param_token_auth()
    test_url_router_trailing_slash_flexibility()
    test_multi_cookie_header_session_auth()
    test_non_string_channel_identifiers()
    test_large_payload_multi_broadcast()
    test_custom_subprotocol_negotiation()
    test_init_ws_decoder_and_subprotocol()
    test_cluster_config_initialization()
