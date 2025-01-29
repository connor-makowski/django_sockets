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
base_socket_server.subscribe("basic_function_big")
# Broadcast a message that will be larger than 1MB to trigger the big data handling
base_socket_server.broadcast(
    "basic_function_big", {f"key{i}": f"val{i}" for i in range(1024 * 256)}
)
# Give the async functions some time to complete
time.sleep(1)

if PASS:
    print("02_basic_function_big.py: PASS")
else:
    print("02_basic_function_big.py: FAIL")
