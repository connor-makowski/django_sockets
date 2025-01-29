from django_sockets.sockets import BaseSocketServer
import asyncio, time, os

CONNECTION_ACCEPTED = False
CONNECT_FN_CALLED = False
RECEIVE_FN_CALLED = False
SEND_RECEIVED_BROADCAST = False
SOMETHING_FAILED = False


class CustomSocketServer(BaseSocketServer):
    def receive(self, data):
        if data == {"data": "test"}:
            global RECEIVE_FN_CALLED
            RECEIVE_FN_CALLED = True
        else:
            global SOMETHING_FAILED
            SOMETHING_FAILED = True
        self.broadcast(self.scope["username"], data)

    def connect(self):
        global CONNECT_FN_CALLED
        CONNECT_FN_CALLED = True
        self.subscribe(self.scope["username"])


async def send(data):
    if data == {"type": "websocket.accept"}:
        global CONNECTION_ACCEPTED
        CONNECTION_ACCEPTED = True
    elif data == {"type": "websocket.send", "text": '{"data": "test"}'}:
        global SEND_RECEIVED_BROADCAST
        SEND_RECEIVED_BROADCAST = True
    else:
        global SOMETHING_FAILED
        SOMETHING_FAILED = True


custom_receive = asyncio.Queue()
custom_socket_server = CustomSocketServer(
    scope={"username": "adam"},
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
custom_receive.put_nowait({"type": "websocket.connect"})
time.sleep(0.2)
custom_receive.put_nowait(
    {"type": "websocket.receive", "text": '{"data": "test"}'}
)
time.sleep(0.2)
custom_receive.put_nowait({"type": "websocket.disconnect"})
time.sleep(0.2)
custom_receive.put_nowait(
    {"type": "websocket.receive", "text": '{"data_after_close": "test"}'}
)
time.sleep(0.2)

PASS = (
    CONNECTION_ACCEPTED
    and CONNECT_FN_CALLED
    and RECEIVE_FN_CALLED
    and SEND_RECEIVED_BROADCAST
    and not SOMETHING_FAILED
)

# print("CONNECTION_ACCEPTED:", CONNECTION_ACCEPTED)
# print("CONNECT_FN_CALLED:", CONNECT_FN_CALLED)
# print("RECEIVE_FN_CALLED:", RECEIVE_FN_CALLED)
# print("SEND_RECEIVED_BROADCAST:", SEND_RECEIVED_BROADCAST)
# print("SOMETHING_FAILED:", SOMETHING_FAILED)

if PASS:
    print("05_socket_lifecycle.py: PASS")
else:
    print("05_socket_lifecycle.py: FAIL")
