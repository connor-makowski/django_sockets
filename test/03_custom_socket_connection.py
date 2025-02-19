from django_sockets.sockets import BaseSocketServer
import asyncio, time, os

PASS = False


class CustomSocketServer(BaseSocketServer):
    def connect(self):
        global PASS
        PASS = True


async def send(ws_data):
    pass


custom_receive = asyncio.Queue()
custom_socket_server = CustomSocketServer(
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
custom_receive.put_nowait({"type": "websocket.connect"})
# Give the async functions a small amount of time to complete
time.sleep(0.2)

if PASS:
    print("03_custom_socket_connection.py: PASS")
else:
    print("03_custom_socket_connection.py: FAIL")
