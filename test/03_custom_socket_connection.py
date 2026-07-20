from django_sockets.sockets import BaseSocketServer
import asyncio, time, os


def test_custom_socket_connection():
    state = {"CONNECT_FN_CALLED": False}

    class CustomSocketServer(BaseSocketServer):
        def connect(self):
            state["CONNECT_FN_CALLED"] = True

    received_messages = []

    async def send(ws_data):
        received_messages.append(ws_data)

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

    custom_socket_server.__kill__()

    assert state["CONNECT_FN_CALLED"] is True
    assert len(received_messages) == 1
    assert received_messages[0] == {"type": "websocket.accept"}
    print("03_custom_socket_connection.py: PASS")


if __name__ == "__main__":
    test_custom_socket_connection()
