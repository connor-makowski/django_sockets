from django_sockets.sockets import BaseSocketServer
import asyncio, time, os

PASS = False


# Override the send method to update the PASS variable if a subscribed broadcast is received and sent
async def send(ws_data):
    global PASS
    PASS = True


# Test the socket server cache process
base_receive = asyncio.Queue()
base_socket_server = BaseSocketServer(
    scope={},
    receive=base_receive.get,
    send=send,
    hosts=[
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ],
)
base_socket_server.start_listeners()
base_socket_server.subscribe("basic_function")
base_socket_server.broadcast("basic_function", "test message")
# Give the async functions a small amount of time to complete
time.sleep(0.2)

if PASS:
    print("01_basic_function.py: PASS")
else:
    print("01_basic_function.py: FAIL")
