from django_sockets.sockets import (
    BaseSocketServer,
    __default_ws_encoder__,
)
import asyncio, time, os, orjson


def test_default_ws_encoder_non_str_keys():
    # 1. Integer keys
    int_dict = {1: "one", 2: "two", 100: "hundred"}
    encoded_int = __default_ws_encoder__(int_dict)
    assert orjson.loads(encoded_int) == {"1": "one", "2": "two", "100": "hundred"}

    # 2. Boolean keys
    bool_dict = {True: "yes", False: "no"}
    encoded_bool = __default_ws_encoder__(bool_dict)
    assert orjson.loads(encoded_bool) == {"true": "yes", "false": "no"}

    # 3. Float keys
    float_dict = {1.5: "one point five", 2.25: "two point two five"}
    encoded_float = __default_ws_encoder__(float_dict)
    assert orjson.loads(encoded_float) == {
        "1.5": "one point five",
        "2.25": "two point two five",
    }

    # 4. Nested structures with mixed non-string keys
    nested_dict = {
        "items": {1: "a", 2: "b"},
        "flags": {True: [1, 2, {3: "nested"}]},
    }
    encoded_nested = __default_ws_encoder__(nested_dict)
    assert orjson.loads(encoded_nested) == {
        "items": {"1": "a", "2": "b"},
        "flags": {"true": [1, 2, {"3": "nested"}]},
    }
    print("12_non_string_keys.py (encoder_unit): PASS")


def test_socket_send_non_str_keys():
    received_messages = []

    async def send(ws_data):
        received_messages.append(ws_data)

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]

    server = BaseSocketServer(scope={}, receive=q.get, send=send, hosts=hosts)
    server.start_listeners()
    time.sleep(0.1)

    # Send data with integer keys via server.send()
    server.send({1: "one", 2: "two"})
    time.sleep(0.1)

    server.__kill__()

    assert len(received_messages) == 1
    assert received_messages[0]["type"] == "websocket.send"
    assert orjson.loads(received_messages[0]["text"]) == {"1": "one", "2": "two"}
    print("12_non_string_keys.py (socket_send): PASS")


def test_socket_broadcast_non_str_keys():
    received_messages = []

    async def send(ws_data):
        received_messages.append(ws_data)

    q = asyncio.Queue()
    hosts = [
        {
            "address": f"redis://{os.environ.get('CACHE_HOST')}:{os.environ.get('CACHE_PORT')}"
        }
    ]

    server = BaseSocketServer(scope={}, receive=q.get, send=send, hosts=hosts)
    server.start_listeners()

    channel = "test_non_str_keys_chan"
    server.subscribe(channel)
    time.sleep(0.2)

    # Broadcast dictionary with integer, boolean, and nested non-string keys
    payload = {
        100: "alpha",
        200: "beta",
        "nested": {1: "inner_one", 2: "inner_two"},
    }
    server.broadcast(channel, payload)
    time.sleep(0.3)

    server.__kill__()

    assert len(received_messages) == 1
    assert received_messages[0]["type"] == "websocket.send"
    decoded = orjson.loads(received_messages[0]["text"])
    assert decoded == {
        "100": "alpha",
        "200": "beta",
        "nested": {"1": "inner_one", "2": "inner_two"},
    }
    print("12_non_string_keys.py (socket_broadcast): PASS")


if __name__ == "__main__":
    test_default_ws_encoder_non_str_keys()
    test_socket_send_non_str_keys()
    test_socket_broadcast_non_str_keys()
