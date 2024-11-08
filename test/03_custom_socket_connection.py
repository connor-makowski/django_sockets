from django_sockets.sockets import BaseSocketServer
import asyncio, time

DJANGO_SOCKETS_CONFIG = {
    "hosts": [{"address": f"redis://0.0.0.0:6379"}],
}

PASS = False


class CustomSocketServer(BaseSocketServer):
    def connect(self):
        global PASS
        PASS = True


async def send(ws_data):
    pass


custom_receive = asyncio.Queue()
custom_socket_server = CustomSocketServer(
    scope={}, receive=custom_receive.get, send=send
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
