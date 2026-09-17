from django_sockets.sockets import BaseSocketServer
from django_sockets.broadcaster import Broadcaster
import asyncio, time, os, json


def test_async_receive():
    state = {"received_data": None}

    class AsyncCustomSocketServer(BaseSocketServer):
        async def receive(self, data):
            state["received_data"] = data

    async def send(ws_data):
        pass

    custom_receive = asyncio.Queue()
    custom_socket_server = AsyncCustomSocketServer(
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
    time.sleep(0.1)
    custom_receive.put_nowait(
        {"type": "websocket.receive", "text": '{"data": "async receive test"}'}
    )
    time.sleep(0.1)

    custom_socket_server.__kill__()

    assert state["received_data"] == {"data": "async receive test"}
    print("10_async_receive_and_multi_broadcast.py (async_receive): PASS")


def test_async_connect():
    state = {"connected": False, "channel_subscribed": None}
    sent_messages = []

    class AsyncConnectSocketServer(BaseSocketServer):
        async def connect(self):
            await asyncio.sleep(0.01)
            state["connected"] = True
            self.channel_id = "async_conn_chan"
            await self.async_subscribe(self.channel_id)
            state["channel_subscribed"] = self.channel_id

    async def send(ws_data):
        sent_messages.append(ws_data)

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]
    server = AsyncConnectSocketServer(
        scope={}, receive=q.get, send=send, hosts=hosts
    )
    server.start_listeners()
    time.sleep(0.1)

    # Trigger connect event
    q.put_nowait({"type": "websocket.connect"})
    time.sleep(0.1)

    server.__kill__()

    assert state["connected"] is True
    assert state["channel_subscribed"] == "async_conn_chan"
    assert any(msg.get("type") == "websocket.accept" for msg in sent_messages)
    print("10_async_receive_and_multi_broadcast.py (async_connect): PASS")


def test_async_connect_and_receive_integration():
    state = {"connected": False, "received": []}
    sent_messages = []

    class FullAsyncSocketServer(BaseSocketServer):
        async def connect(self):
            state["connected"] = True
            self.channel_id = "full_async_chan"
            await self.async_subscribe(self.channel_id)

        async def receive(self, data):
            state["received"].append(data)
            # Echo response asynchronously via broadcast
            await self.async_broadcast(self.channel_id, {"echo": data})

    async def send(ws_data):
        sent_messages.append(ws_data)

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]
    server = FullAsyncSocketServer(
        scope={}, receive=q.get, send=send, hosts=hosts
    )
    server.start_listeners()
    time.sleep(0.1)

    # 1. Connect
    q.put_nowait({"type": "websocket.connect"})
    time.sleep(0.1)

    assert state["connected"] is True

    # 2. Receive
    q.put_nowait(
        {
            "type": "websocket.receive",
            "text": '{"action": "ping", "id": 123}',
        }
    )
    time.sleep(0.1)

    server.__kill__()

    assert len(state["received"]) == 1
    assert state["received"][0] == {"action": "ping", "id": 123}

    # Verify broadcast echo was received by the socket
    decoded_sends = [
        json.loads(m["text"])
        for m in sent_messages
        if m.get("type") == "websocket.send" and "text" in m
    ]
    assert {"echo": {"action": "ping", "id": 123}} in decoded_sends
    print(
        "10_async_receive_and_multi_broadcast.py (async_connect_receive_integration): PASS"
    )


def test_async_disconnect():
    state = {"disconnected": False, "code": None}

    class AsyncDisconnectSocketServer(BaseSocketServer):
        async def disconnect(self, code=1000):
            await asyncio.sleep(0.01)
            state["disconnected"] = True
            state["code"] = code

    async def send(ws_data):
        pass

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]
    server = AsyncDisconnectSocketServer(
        scope={}, receive=q.get, send=send, hosts=hosts
    )
    server.start_listeners()
    time.sleep(0.1)

    q.put_nowait({"type": "websocket.disconnect", "code": 4002})
    time.sleep(0.1)

    assert state["disconnected"] is True
    assert state["code"] == 4002
    print("10_async_receive_and_multi_broadcast.py (async_disconnect): PASS")


def test_multi_channel_broadcast():
    received_ch1 = []
    received_ch2 = []

    async def send1(ws_data):
        received_ch1.append(ws_data)

    async def send2(ws_data):
        received_ch2.append(ws_data)

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

    s1.subscribe("chan_alpha")
    s2.subscribe("chan_beta")
    time.sleep(0.1)

    # Broadcast to multiple channels using a list in broadcast()
    s1.broadcast(["chan_alpha", "chan_beta"], {"alert": "multi-broadcast"})
    time.sleep(0.1)

    s1.__kill__()
    s2.__kill__()

    assert len(received_ch1) == 1
    assert len(received_ch2) == 1
    assert json.loads(received_ch1[0]["text"]) == {"alert": "multi-broadcast"}
    assert json.loads(received_ch2[0]["text"]) == {"alert": "multi-broadcast"}
    print("10_async_receive_and_multi_broadcast.py (multi_broadcast): PASS")


def test_raw_send_bypass():
    received_raw = []

    async def send_raw(ws_data):
        received_raw.append(ws_data)

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]
    s = BaseSocketServer(scope={}, receive=q.get, send=send_raw, hosts=hosts)
    s.start_listeners()

    s.send('{"already_encoded": true}', raw=True)
    time.sleep(0.1)

    s.__kill__()

    assert len(received_raw) == 1
    assert received_raw[0] == {
        "type": "websocket.send",
        "text": '{"already_encoded": true}',
    }
    print("10_async_receive_and_multi_broadcast.py (raw_send): PASS")


if __name__ == "__main__":
    test_async_receive()
    test_async_connect()
    test_async_connect_and_receive_integration()
    test_async_disconnect()
    test_multi_channel_broadcast()
    test_raw_send_bypass()
