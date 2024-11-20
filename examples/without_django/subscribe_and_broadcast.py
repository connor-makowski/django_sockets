from django_sockets.sockets import BaseSocketServer
import asyncio, time

# Override the send method to print the data being sent
async def send(data):
    """
    Normally you would not override the send method, but since we are not actually sending data over a websocket connection
    we are just going to print the data that would be sent.

    This is useful for testing the socket server without having to actually send data over a websocket connection

    Note: This only prints the first 128 characters of the data
    """
    print("WS SENDING:", str(data)[:128])

# Create a receive queue to simulate receiving messages from a websocket client
base_receive = asyncio.Queue()
# Create a base socket server with a scope of {}
base_socket_server = BaseSocketServer(
    scope={}, 
    receive=base_receive.get, 
    send=send, 
    hosts=[{"address": f"redis://0.0.0.0:6379"}]
)

# Send a message that does not require a cache server
base_socket_server.send("test message (send)")
# Start the listeners for the base socket server
base_socket_server.start_listeners()
# Subscribe to the test_channel
base_socket_server.subscribe("test_channel")
# Broadcast a message to the test_channel
base_socket_server.broadcast("test_channel", "test message (broadcast)")
# Give the async functions a small amount of time to complete
time.sleep(.5)

#=> Output:
#=> WS SENDING: {'type': 'websocket.send', 'text': '"test message (send)"'}
#=> WS SENDING: {'type': 'websocket.send', 'text': '"test message (broadcast)"'}