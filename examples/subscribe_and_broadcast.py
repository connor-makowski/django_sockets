from django_sockets.sockets import BaseSocketServer
import asyncio, time

DJANGO_SOCKETS_CONFIG = {
    "hosts": [
        {"address": f"redis://0.0.0.0:6379"}
    ],
}

# Override the send method to print the data being sent
# instead of sending it over a non existent websocket connection
async def send(ws_data):
    print("WS SENDING:", ws_data)


# Create a receive queue to simulate receiving messages from a websocket client
base_receive = asyncio.Queue()
# Create a base socket server with a scope of {}
base_socket_server = BaseSocketServer(scope={}, receive=base_receive.get, send=send, config=DJANGO_SOCKETS_CONFIG)
# Start the listeners for the base socket server
base_socket_server.start_listeners()
# Subscribe to the test_channel
base_socket_server.subscribe("test_channel")
# Broadcast a message to the test_channel
base_socket_server.broadcast("test_channel", "test message")
# Give the async functions a small amount of time to complete
time.sleep(.5)


# Output:
#=> WS SENDING: {'type': 'websocket.send', 'text': '"test message"'}