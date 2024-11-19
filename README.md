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

- <b>Redis / Valkey Cache Server</b>: If you plan to `broadcast` messages across clients and not just respond to individual clients, make sure a cache (valkey or redis) is setup and accessible from your server. 
    <details>
    <summary>Expand this to setup a local valkey cache using Docker.</summary>

    - Create and start a valkey cache server using docker:
        ```bash
        docker run -d -p 6379:6379 --name django_sockets_cache valkey/valkey:7
        ```
    - To run the container after it has been stopped:
        ```bash
        docker start django_sockets_cache
        ```
    - To kill the container later:
        ```bash
        docker kill django_sockets_cache
        ```
    </details>

# Usage

Low level docs: https://connor-makowski.github.io/django_sockets/django_sockets.html

## Example Usage

### Use In Django

1. Make sure a redis / valkey cache server is running.
2. Install Requirements:
    ```bash
    pip install django_sockets
    ```
    - Note: This would normally be done via your `requirements.txt` file and installed in a virtual environment.
3. Create a new Django project (if you don't already have one) and navigate to the project directory:
    ```sh
    python3 -m django startproject myapp
    cd myapp
    ```
4. Add `ASGI_APPLICATION` above your `INSTALLED_APPS` and add `'daphne'` to your `INSTALLED_APPS` in your `settings.py` file
    `myapp/settings.py`
    ```py
    ASGI_APPLICATION = 'myapp.asgi.application'
    INSTALLED_APPS = [
        'daphne',
        # Your other installed apps
        ]
    ```
5. Create a new file called `ws.py` and place it in `myapp`.
    `myapp/ws.py`
    ```py
    from django.urls import path
    from django_sockets.middleware import AuthMiddlewareStack
    from django_sockets.sockets import BaseSocketServer
    from django_sockets.utils import URLRouter

        
    class SocketServer(BaseSocketServer):
        def configure(self):
            '''
            This method is optional and only needs to be defined 
            if you are broadcasting or subscribing to channels.

            It is not required if you just plan to respond to
            individual websocket clients.

            This method is used during the initialization of the
            socket server to define the cache hosts that will be
            used for broadcasting and subscribing to channels.
            '''
            self.hosts = [{"address": "redis://0.0.0.0:6379"}]

        def connect(self):
            '''
            This method is optional and is called when a websocket
            client connects to the server. 
            
            It can be used for a variety of purposes such as 
            subscribing to a channel.
            '''
            # When a client connects, create a channel_id attribute 
            # that is set to the user's id. This allows for user scoped 
            # channels if you are using the AuthMiddlewareStack.
            # Note: Since we are not using authentication, all 
            # clients will be subscribed to the same channel ('None').
            self.channel_id = str(self.scope['user'].id)
            self.subscribe(self.channel_id)

        def receive(self, data):
            '''
            This method is called when a websocket client sends
            data to the server. It can be used to:
                - Execute Custom Logic
                - Update the state of the server
                - Send data back to the client
                - Subscribe to a channel
                - Broadcast data to be sent to subscribed clients
            '''
            if data.get('command')=='reset':
                data['counter']=0
            elif data.get('command')=='increment':
                data['counter']+=1
            else:
                raise ValueError("Invalid command")
            # Broadcast the update to all websocket clients 
            # subscribed to this socket's channel_id
            self.broadcast(self.channel_id, data)
            # Alternatively if you just want to respond to the 
            # current socket client, just use self.send(data):
            # self.send(data)


    def get_ws_asgi_application():
        '''
        Define the websocket routes for the Django application.

        You can have multiple websocket routes defined here.

        This is the place to apply any needed middleware.
        '''
        # Note: `AuthMiddlewareStack` is not required, but is useful 
        # for user scoped channels.
        return AuthMiddlewareStack(URLRouter([
            path("ws/", SocketServer.as_asgi),
        ]))
    ```
6. Modify your `asgi.py` file to use the `django_sockets` `ProtocolTypeRouter` and add your app to your websocket routes:
    `myapp/asgi.py`
    ```py
    import os

    from django.core.asgi import get_asgi_application
    from django_sockets.utils import ProtocolTypeRouter
    from .ws import get_ws_asgi_application

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')

    asgi_app = get_asgi_application()
    ws_asgi_app = get_ws_asgi_application()

    application = ProtocolTypeRouter(
        {
            "http": asgi_app,
            "websocket": ws_asgi_app,
        }
    )
    ```
7. In the project root, create `templates/client.html` and add the following client code:
    `templates/client.html`
    ```html
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WebSocket Client</title>
    </head>
    <body>
        <h1>WebSocket Client</h1>
        <div>
            <button id="resetBtn">Reset Counter</button>
            <button id="incrementBtn">Increment Counter</button>
        </div>
        <div>
            <h3>Messages:</h3>
            <pre id="messages"></pre>
        </div>

        <script>
            // Connect to the WebSocket server
            const wsUrl = "ws://localhost:8000/ws/";
            const websocket = new WebSocket(wsUrl);
            var counter = 0;

            // DOM elements
            const messages = document.getElementById("messages");
            const resetBtn = document.getElementById("resetBtn");
            const incrementBtn = document.getElementById("incrementBtn");

            // Helper function to display messages
            const displayMessage = (msg) => {
                messages.textContent += msg + "\n";
            };

            // Handle WebSocket events
            websocket.onopen = () => {
                displayMessage("WebSocket connection established.");
            };

            websocket.onmessage = (event) => {
                displayMessage("Received: " + event.data);
                counter = JSON.parse(event.data).counter;
            };

            websocket.onerror = (error) => {
                displayMessage("WebSocket error: " + error);
            };

            websocket.onclose = () => {
                displayMessage("WebSocket connection closed.");
            };

            // Send 'reset' command
            resetBtn.addEventListener("click", () => {
                const command = { command: "reset" };
                websocket.send(JSON.stringify(command));
                displayMessage("Sent: " + JSON.stringify(command));
            });

            // Send 'increment' command
            incrementBtn.addEventListener("click", () => {
                const command = { "command": "increment", "counter": counter };
                websocket.send(JSON.stringify(command));
                displayMessage("Sent: " + JSON.stringify(command));
            });
        </script>
    </body>
    </html>
    ```

8. In `settings.py` update `DIRS` in your `TEMPLATES` to include your new template directory:
    `myapp/settings.py`
    ```py
    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [BASE_DIR / 'templates'], # Modify this line
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                ],
            },
        },
    ]
    ```

9. In `urls.py` add a simple `clent_view` to render the `client.html` template and set at it the root URL.
    `myapp/urls.py`
    ```py
    from django.contrib import admin
    from django.shortcuts import render
    from django.urls import path

    def client_view(request):
        '''
        Render the client.html template
        '''
        return render(request, 'client.html')

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('', client_view),
    ]
    ```
    - Note: Normally something like `client_view` would be imported from a `views.py` file, but for simplicity it is defined here.

10. Make migrations, migrate, create a superuser and run the server (from the project root)
    ```sh
    python manage.py makemigrations
    python manage.py migrate
    python manage.py runserver
    ```
11. Open your browser and navigate to `http://localhost:8000/` to see the client page. 
    - Open up a second tab and navigate to the same URL. You should see the counter incrementing and resetting in both tabs.
    - Note: The counter state is maintained client side. 
        - If one tab joins after the other has modified the counter, it will not be in sync.
        - Whichever counter fires first will determine the next counter value for both tabs.






## Non Django Usage

### Example Subscribing & Broadcasting
```py
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
```

### Example Handle Websocket Messages
```py
from django_sockets.sockets import BaseSocketServer
import asyncio, time

class CustomSocketServer(BaseSocketServer):
    def connect(self):
        """
        When the websocket connects, subscribe to the channel of the user.

        This is an important method to override if you want to subscribe to a channel when a user frist connects.

        Otherwise, you can always subscribe to a channel based on the data that is received in the receive method.
        """
        print(f"CONNECTED")
        print(f"SUSCRIBING TO '{self.scope['username']}'")
        self.subscribe(self.scope['username'])

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

# Override the send method to print the data being sent
async def send(data):
    """
    Normally you would not override the send method, but since we are not actually sending data over a websocket connection
    we are just going to print the data that would be sent.

    This is useful for testing the socket server without having to actually send data over a websocket connection

    Note: This only sends the first 128 characters of the data
    """
    print("WS SENDING:", str(data)[:128])

# Create a receive queue to simulate receiving messages from a websocket client
custom_receive = asyncio.Queue()
# Create a custom socket server defined above with a scope of {'username':'adam'}, the custom_receive queue, and the send method defined above
custom_socket_server = CustomSocketServer(
    scope={'username':'adam'}, 
    receive=custom_receive.get, 
    send=send, 
    hosts=[{"address": f"redis://0.0.0.0:6379"}]
)
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
