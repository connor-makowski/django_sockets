from django_sockets.sockets import BaseSocketServer
import asyncio, time, os


def test_socket_lifecycle():
    state = {
        "CONNECTION_ACCEPTED": False,
        "CONNECT_FN_CALLED": False,
        "RECEIVE_FN_CALLED": False,
        "SEND_RECEIVED_BROADCAST": False,
        "SOMETHING_FAILED": False,
        "DISCONNECT_FN_CALLED": False,
        "DISCONNECT_CODE": None,
    }

    class CustomSocketServer(BaseSocketServer):
        def receive(self, data):
            if data == {"data": "test"}:
                state["RECEIVE_FN_CALLED"] = True
            else:
                state["SOMETHING_FAILED"] = True
            self.broadcast(self.scope["username"], data)

        def connect(self):
            state["CONNECT_FN_CALLED"] = True
            self.subscribe(self.scope["username"])

        def disconnect(self, code):
            state["DISCONNECT_FN_CALLED"] = True
            state["DISCONNECT_CODE"] = code

    async def send(data):
        if data == {"type": "websocket.accept"}:
            state["CONNECTION_ACCEPTED"] = True
        elif data == {"type": "websocket.send", "text": '{"data": "test"}'}:
            state["SEND_RECEIVED_BROADCAST"] = True
        else:
            state["SOMETHING_FAILED"] = True

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
    custom_receive.put_nowait({"type": "websocket.disconnect", "code": 1000})
    time.sleep(0.2)
    custom_receive.put_nowait(
        {"type": "websocket.receive", "text": '{"data_after_close": "test"}'}
    )
    time.sleep(0.2)

    assert state["CONNECTION_ACCEPTED"] is True
    assert state["CONNECT_FN_CALLED"] is True
    assert state["RECEIVE_FN_CALLED"] is True
    assert state["SEND_RECEIVED_BROADCAST"] is True
    assert state["DISCONNECT_FN_CALLED"] is True
    assert state["DISCONNECT_CODE"] == 1000
    assert state["SOMETHING_FAILED"] is False
    print("05_socket_lifecycle.py: PASS")


if __name__ == "__main__":
    test_socket_lifecycle()
