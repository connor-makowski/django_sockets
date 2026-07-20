from django_sockets.sockets import BaseSocketServer
import asyncio, time, os
import json


def test_basic_function_big():
    received_messages = []

    # Override the send method to capture received messages
    async def send(ws_data):
        received_messages.append(ws_data)

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
    payload = {f"key{i}": f"val{i}" for i in range(1024 * 256)}
    base_socket_server.broadcast("basic_function_big", payload)
    # Give the async functions some time to complete
    time.sleep(1)

    base_socket_server.__kill__()

    assert len(received_messages) == 1
    assert json.loads(received_messages[0]["text"]) == payload
    print("02_basic_function_big.py: PASS")


if __name__ == "__main__":
    test_basic_function_big()
