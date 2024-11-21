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

    - Install Docker: https://docs.docker.com/get-docker/
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

- Low level docs: https://connor-makowski.github.io/django_sockets/django_sockets.html
- [Working django and non django examples can be found here](https://github.com/connor-makowski/django_sockets/tree/main/examples).

## Examples

### Example: Simple Counter

1. Make sure a redis / valkey cache server is running.
2. Install Requirements:

    `shell`
    ```bash
    pip install django_sockets
    ```
    - Note: This would normally be done via your `requirements.txt` file and installed in a virtual environment.
3. Create a new Django project (if you don't already have one) and navigate to the project directory:

    `shell`
    ```sh
    python3 -m django startproject myapp
    cd myapp
    ```
4. Modify your settings file:
    - Add `ASGI_APPLICATION` above your `INSTALLED_APPS`
    - Add `'daphne'` to the top of your `INSTALLED_APPS` in your `settings.py` file
        - Daphne is the django created ASGI server that is used by `django_sockets`.
    
    `myapp/settings.py`
    ```py
    ASGI_APPLICATION = 'myapp.asgi.application'
    INSTALLED_APPS = [
        'daphne',
        # Your other installed apps
        ]
    ```
5. Create a new file called `ws.py` and place it in `myapp`.
    - This file will hold the websocket server logic.
    - Define a `SocketServer` class that extends `BaseSocketServer`.
        - Define a `configure` method to set the cache hosts.
        - Define a `connect` method to handle logic when a client connects.
        - Define a `receive` method to handle logic when a client sends data.
    - Define a `get_ws_asgi_application` function that returns a URL Router with the websocket routes.
        - This is where you can apply any needed middleware.

    `myapp/ws.py`
    ```py
    from django.urls import path
    from django_sockets.middleware import SessionAuthMiddleware
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
            # channels if you are using auth middleware.
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
        # Note: `SessionAuthMiddleware` is not required, but is useful 
        # for user scoped channels.
        return SessionAuthMiddleware(URLRouter([
            path("ws/", SocketServer.as_asgi),
        ]))
    ```
6. Modify your `asgi.py` file:
    - Use the `django_sockets` `ProtocolTypeRouter`
    - Based on the protocol type, return the appropriate ASGI application.

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
7. In the project root, create `templates/client.html`:
    - This will be the client side of the websocket connection.
    - It will contain a simple counter that can be incremented and reset.
    - The client will send commands to the server to reset or increment the counter.
    - The server will handle the commands and broadcast or send the updated counter relevant clients.

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
        <h2>User: {{ user.username }}</h2>
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

8. In `settings.py`:
    - Update `DIRS` in your `TEMPLATES` to include your new template directory

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

9. In `urls.py`:
    - Add a simple `clent_view` to render the `client.html` template
    - Set at it the root URL

    `myapp/urls.py`
    ```py
    from django.contrib import admin
    from django.shortcuts import render
    from django.urls import path

    def client_view(request):
        '''
        Render the client.html template
        '''
        # Pass the user to the client.html template
        return render(request, 'client.html', {'user': request.user})

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('', client_view),
    ]
    ```
    - Note: Normally something like `client_view` would be imported from a `views.py` file, but for simplicity it is defined here.

10. Setup and run the server:
    - Make any needed migrations (determine if the database needs to be created or updated)
    - Migrate any changes to bring the database up to date
    - Run the server

    `shell`
    ```sh
    python manage.py makemigrations
    python manage.py migrate
    python manage.py runserver
    ```
11. Open your browser:
    - Navigate to `http://localhost:8000/` to see the client page. 
    - Duplicate the tab. 
        - You should see the counter incrementing and resetting in both tabs.
    - Note: The counter state is maintained client side. 
        - If one tab joins after the other has modified the counter, it will not be in sync.
        - Whichever counter fires first will determine the next counter value for both tabs.
    - Note: Since you have not logged in yet, your Auth Middleware will just return an Anonymous User.
        - This means that all users are subscribed to the same channel from the user id ('None').
        - Once users are logged in, they will be subscribed to their own user id channel.
12. To avoid creating a custom login page, we will just use a superuser and take advantage of the admin login page.
    - To create a superuser, you can run the following command:
        ```bash
        python manage.py createsuperuser
        ```
        - Follow the prompts to create a superuser.
    - Login at `http://localhost:8000/admin/login/?next=/` with your superuser credentials.
        - You can logout by navigating to `http://localhost:8000/admin/` and clicking the logout button.
    - You should now see a functional counter page with websockets scoped to the logged in user.

<br/><hr/><br/>

### Example: Simple Counter Extension 
#### Use DjangoRestFramework for Token Authentication instead of Session based Authentication

1. Complete all steps in the previous example.
2. Install DjangoRestFramework:

    `shell`
    ```bash
    pip install djangorestframework
    ```
3. Modify your `settings.py` file:
    - Add `'rest_framework.authtoken'` to the end of your `INSTALLED_APPS`

    `myapp/settings.py`
    ```py
    INSTALLED_APPS = [
        'daphne',
        # Your other installed apps,
        'rest_framework.authtoken', # Add this installed app
        ]
    ```
4. Make and run migrations:

    `shell`
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```
5. In your view (specified in `myapp.urls.py`):
    - Ensure you have a DRF Token and pass it to your websocket template.
    - Force users to login before accessing the websocket client.
        - In general, you would want to create a custom login page and use the `@login_required` decorator on your view. 
        - For simplicity, we are just using the admin login page.
    `myapp/urls.py`
    ```py
    from django.contrib import admin
    from django.shortcuts import render
    from django.urls import path

    from rest_framework.authtoken.models import Token # Add this import
    from django.contrib.auth.decorators import login_required # Add this import

    @login_required(login_url="/admin/login/") # Add this decorator
    def client_view(request):
        '''
        Render the client.html template
        '''
        # Get or create a token for the user
        token, created = Token.objects.get_or_create(user=request.user) # Add this line
        # Pass the user and token to the client.html template
        return render(request, 'client.html', {'user': request.user, 'token': token}) # Modify this line

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('', client_view),
    ]
    ```
6. Update your middleware to use the `DRFTokenAuthMiddleware` instead of the `SessionAuthMiddleware`:

    `myapp/ws.py`
    ```py
    from django.urls import path
    from django_sockets.middleware import DRFTokenAuthMiddleware # Modify this line
    from django_sockets.sockets import BaseSocketServer
    from django_sockets.utils import URLRouter

    # Your existing code here

    def get_ws_asgi_application():
        '''
        Define the websocket routes for the Django application.

        You can have multiple websocket routes defined here.

        This is the place to apply any needed middleware.
        '''
        return DRFTokenAuthMiddleware(URLRouter([ # Modify this line
            path("ws/", SocketServer.as_asgi),
        ]))
    ```

7. Update your client to pass the token to the websocket server on connection:
    - Option 1: Use a `sec-websocket-protocol` header to pass the token:
        
        `templates/client.html`
        ```html
        const websocket = new WebSocket(wsUrl,["Token.{{ token }}"]);
        ```
    - Option 2: Use a query parameter to pass the token:
        
        `templates/client.html`
        ```html
        const wsUrl = "ws://localhost:8000/ws/?token={{ token }}";
        const websocket = new WebSocket(wsUrl);
        ```
8. Run the server and navigate to `http://localhost:8000/` to see the client page.
    - You will be redirected to the admin login page.
    - Login with your superuser credentials.
    - You should now see a functional counter page with websockets scoped to the logged in user.

<br/><hr/><br/>