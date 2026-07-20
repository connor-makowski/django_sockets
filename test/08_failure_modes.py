import pytest
import asyncio
import os
import time
from django_sockets.sockets import BaseSocketServer
from django_sockets.pubsub import PubSubLayer, ShardConnection
from django_sockets.utils import ensure_loop_running


def test_failure_modes():
    # 1. WS Encoder Exception Handling (No NameError)
    # Check that calling self.send with a non-encodable type when ws_encoder is json.dumps
    # will enter the exception block, but won't crash the program with a NameError because 'e' is bound.
    custom_socket_server = BaseSocketServer(
        scope={},
        receive=None,
        send=None,
        hosts=[
            {
                "address": f"redis://{os.environ.get('CACHE_HOST', 'localhost')}:{os.environ.get('CACHE_PORT', '6379')}"
            }
        ],
    )

    # We pass an object that cannot be serialized by json.dumps (e.g. a set)
    # This should log the error and handle it without throwing a NameError
    try:
        custom_socket_server.send({complex(1, 2)})
    except Exception as ex:
        pytest.fail(f"Self.send crashed with exception: {ex}")

    # 2. Host Configuration Validation
    # A. hosts is not a list
    with pytest.raises(
        ValueError, match="Hosts must be a list of dictionaries"
    ):
        PubSubLayer(hosts="invalid_hosts")

    # B. hosts list is empty
    with pytest.raises(
        ValueError, match="Hosts must contain at least one dictionary"
    ):
        PubSubLayer(hosts=[])

    # C. Missing sentinels when master_name is provided
    with pytest.raises(KeyError):
        # This will raise a KeyError trying to pop 'sentinels'
        PubSubLayer(hosts=[{"master_name": "mymaster"}])

    # 3. Message Deserialization Failure
    # Verify ShardConnection.__deserialize__ raises error on invalid msgpack bytes
    shard = custom_socket_server.pubsub_layer.shards[0]
    with pytest.raises(Exception):
        shard.__deserialize__(b"invalid_bytes_not_msgpack")

    # 4. ensure_loop_running with Stopped/Closed Loop
    # Create a loop, close it, and see that ensure_loop_running handles it without crash
    new_loop = asyncio.new_event_loop()
    new_loop.close()

    ret_loop = ensure_loop_running(new_loop)
    assert ret_loop != new_loop
    assert not ret_loop.is_closed()

    # 5. Clean termination on kill
    # Verify that calling __kill__ on BaseSocketServer changes is_alive to False
    assert custom_socket_server.is_alive is True
    custom_socket_server.__kill__()
    assert custom_socket_server.is_alive is False

    print("08_failure_modes.py: PASS")


if __name__ == "__main__":
    test_failure_modes()
