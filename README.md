# Django Sockets
[![PyPI version](https://badge.fury.io/py/django_sockets.svg)](https://badge.fury.io/py/django_sockets)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Simplified Django websocket processes designed to work with cloud caches (valkey|redis on single|distributed|serverless)

# Setup

### General

Make sure you have Python 3.10.x (or higher) installed on your system. You can download it [here](https://www.python.org/downloads/).

### Installation

```
pip install django_sockets
```

### Other Requirements

- Make sure a cache (valkey or redis) is setup and accessible from your server.

    - To run one locally (using docker) for testing, you can use the following command:

        ```bash
        docker run -d -p 6379:6379 --name django_sockets_cache valkey/valkey:7
        ```

    - To run the container after it has been created, you can use the following command:

        ```bash
        docker start django_sockets_cache
        ```

    - To kill the container later, you can use the following command:

        ```bash
        docker kill django_sockets_cache
        ```

# Usage

Low level docs: https://connor-makowski.github.io/django_sockets/django_sockets.html

## Implement in a Django Project

### TODO

## Examples Without Django

### Example Subscribing & Broadcasting
```py
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


#=> Output:
#=> WS SENDING: {'type': 'websocket.send', 'text': '"test message"'}
```

### Example Handle Websocket Messages
```py
from django_sockets.sockets import BaseSocketServer
import asyncio, time

DJANGO_SOCKETS_CONFIG = {
    "hosts": [
        {"address": f"redis://0.0.0.0:6379"}
    ],
}

class CustomSocketServer(BaseSocketServer):
    def receive(self, data):
        """
        When a data message is received from a websocket client:
            - Print the data
            - Broadcast the data to a channel (the same channel that the socket server is subscribed to)

        Normally you would want to override the receive method to do any server side processing of the data that is received
        then broadcast any changes back to relevant channels.
        """
        print("WS RECEIVED: ", data)
        print(f"BROADCASTING TO '{self.scope['username']}'")
        self.broadcast(self.scope['username'], data)

    def connect(self):
        """
        When the websocket connects, subscribe to the channel of the user.

        This is an important method to override if you want to subscribe to a channel when a user frist connects.

        Otherwise, you can always subscribe to a channel based on the data that is received in the receive method.
        """
        print(f"CONNECTED")
        print(f"SUSCRIBING TO '{self.scope['username']}'")
        self.subscribe(self.scope['username'])

# Override the send method to print the data being sent
async def send(data):
    """
    Normally you would not override the send method, but since we are not actually sending data over a websocket connection
    we are just going to print the data that would be sent.

    This is useful for testing the socket server without having to actually send data over a websocket connection

    Note: This only sends the first 64 characters of the data
    """
    print("WS SENDING:", str(data)[:64])

# Create a receive queue to simulate receiving messages from a websocket client
custom_receive = asyncio.Queue()
# Create a custom socket server defined above with a scope of {'username':'adam'}, the custom_receive queue, and the send method defined above
custom_socket_server = CustomSocketServer(scope={'username':'adam'}, receive=custom_receive.get, send=send)
# Start the listeners for the custom socket server
#    - Websocket Listener - Listens for websocket messages
#    - Broadcast Listener - Listens for messages that were broadcasted to a channel that the socket server is subscribed to
custom_socket_server.start_listeners()
# Give the async functions a small amount of time to complete
time.sleep(.1)
# Simulate a WS connection request
custom_receive.put_nowait({'type': 'websocket.connect'})
# Give the async functions a small amount of time to complete
time.sleep(.1)
# Simulate a message being received from a WS client
# This will call the receive method which is defined above
custom_receive.put_nowait({'type': 'websocket.receive', 'text': '{"data": "test"}'})
# Give the async functions a small amount of time to complete
time.sleep(.1)
# Simulate a WS disconnect request
custom_receive.put_nowait({'type': 'websocket.disconnect'})
# Give the async functions a small amount of time to complete
time.sleep(.1)
# Simulate a message being received from a WS client after the connection has been closed
# This will not do anything since the connection has been closed and the listeners have been killed
custom_receive.put_nowait({'type': 'websocket.receive', 'text': '{"data_after_close": "test"}'})
# Give the async functions a small amount of time to complete
time.sleep(.1)

#=> Output:
#=> WS SENDING: {'type': 'websocket.accept'}
#=> CONNECTED
#=> SUSCRIBING TO 'adam'
#=> WS RECEIVED:  {'data': 'test'}
#=> BROADCASTING TO 'adam'
#=> WS SENDING: {'type': 'websocket.send', 'text': '{"data": "test"}'}

```
