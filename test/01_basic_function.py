from django_sockets.sockets import BaseSocketServer
import asyncio, time, os


def test_basic_function():
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
    base_socket_server.subscribe("basic_function")
    base_socket_server.broadcast("basic_function", "test message")
    # Give the async functions a small amount of time to complete
    time.sleep(0.2)

    base_socket_server.__kill__()

    assert len(received_messages) == 1
    assert received_messages[0] == {
        "type": "websocket.send",
        "text": '"test message"',
    }
    print("01_basic_function.py: PASS")


if __name__ == "__main__":
    test_basic_function()
