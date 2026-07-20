from django_sockets.sockets import BaseSocketServer
import asyncio, time, os


def test_custom_socket_receive():
    state = {"received_data": None}

    class CustomSocketServer(BaseSocketServer):
        def receive(self, data):
            state["received_data"] = data

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
    custom_receive.put_nowait(
        {"type": "websocket.receive", "text": '{"data": "test data"}'}
    )
    # Give the async functions a small amount of time to complete
    time.sleep(0.2)

    custom_socket_server.__kill__()

    assert state["received_data"] == {"data": "test data"}
    print("04_custom_socket_receive.py: PASS")


if __name__ == "__main__":
    test_custom_socket_receive()
