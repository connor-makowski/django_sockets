# Django Sockets Tutorial

This step-by-step guide walks you through building a real-time counter application using `django_sockets`.

---

## Part 1: Simple Counter (Session Authentication)

Follow these steps to set up a real-time, user-scoped counter application.

### 1. Prerequisites
Ensure you have a Valkey/Redis cache server running. If you have Docker installed, you can start one with:
```bash
docker run -d -p 6379:6379 --name django_sockets_cache valkey/valkey:7
```

### 2. Create the Project
Install Django and `django_sockets`, create a new Django project, and navigate to the project directory:
```bash
pip install django_sockets django
django-admin startproject myapp
cd myapp
```

### 3. Implement the Socket Server
Create a new file `myapp/ws.py` to define the WebSocket server logic:
```python
from django.urls import path
from django_sockets.middleware import SessionAuthMiddleware
from django_sockets.sockets import BaseSocketServer
from django_sockets.utils import URLRouter


class SocketServer(BaseSocketServer):
    def configure(self):
        """
        Optional: Define the cache hosts used for broadcasting
        and subscribing to channels.
        """
        self.hosts = [{"address": "redis://localhost:6379"}]

    def connect(self):
        """
        Called when a WebSocket client connects. We subscribe the client
        to a user-scoped channel using their user ID.
        """
        self.channel_id = str(self.scope["user"].id)
        self.subscribe(self.channel_id)

    def receive(self, data):
        """
        Called when a client sends JSON data. Updates the counter
        and broadcasts it to the channel.
        """
        if data.get("command") == "reset":
            data["counter"] = 0
        elif data.get("command") == "increment":
            data["counter"] += 1
        else:
            raise ValueError("Invalid command")

        # Broadcast the message to all subscribers of this channel
        self.broadcast(self.channel_id, data)


def get_ws_asgi_application():
    """
    Define WebSocket routes and apply Session authentication middleware.
    """
    return SessionAuthMiddleware(
        URLRouter(
            [
                path("ws/", SocketServer.as_asgi),
            ]
        )
    )
```

### 4. Configure ASGI Entrypoint
Modify `myapp/asgi.py` to route HTTP and WebSocket traffic.
> [!IMPORTANT]
> Always call `get_asgi_application()` and configure settings **before** importing `django_sockets` routing or middleware to prevent Django initialization race conditions.

```python
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myapp.settings")
asgi_app = get_asgi_application()

# Import websocket routing after Django initialization
from django_sockets.utils import ProtocolTypeRouter
from .ws import get_ws_asgi_application

ws_asgi_app = get_ws_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": asgi_app,
        "websocket": ws_asgi_app,
    }
)
```

### 5. Create the Frontend Client
Create a new directory called `templates` in your project root, then create `templates/client.html`:
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
        const wsUrl = "ws://localhost:8000/ws/";
        const websocket = new WebSocket(wsUrl);
        let counter = 0;

        const messages = document.getElementById("messages");
        const resetBtn = document.getElementById("resetBtn");
        const incrementBtn = document.getElementById("incrementBtn");

        const displayMessage = (msg) => {
            messages.textContent += msg + "\n";
        };

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

        resetBtn.addEventListener("click", () => {
            const command = { command: "reset" };
            websocket.send(JSON.stringify(command));
            displayMessage("Sent: " + JSON.stringify(command));
        });

        incrementBtn.addEventListener("click", () => {
            const command = { "command": "increment", "counter": counter };
            websocket.send(JSON.stringify(command));
            displayMessage("Sent: " + JSON.stringify(command));
        });
    </script>
</body>
</html>
```

### 6. Register Templates & Views
Configure `myapp/settings.py` to read the templates directory:
```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
```

Add the view and URL route in `myapp/urls.py`:
```python
from django.contrib import admin
from django.shortcuts import render
from django.urls import path


def client_view(request):
    return render(request, "client.html", {"user": request.user})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", client_view),
]
```

### 7. Run the Server
Run migrations and start Uvicorn:
```bash
python manage.py makemigrations
python manage.py migrate
uvicorn myapp.asgi:application --reload
```
Navigate to `http://localhost:8000/`. When logged out, the client connects as `AnonymousUser` and shares the `"None"` channel.

To test user-scoped channels:
1. Create a superuser: `python manage.py createsuperuser`.
2. Navigate to `http://localhost:8000/admin/login/?next=/` and log in.
3. Once logged in, your WebSocket connection will be scoped specifically to your user ID.

---

## Part 2: Django Rest Framework (Token Authentication)

To migrate from Session-based authentication to Django Rest Framework token-based authentication:

### 1. Install Dependencies
```bash
pip install djangorestframework
```

### 2. Configure Settings
Add `'rest_framework.authtoken'` to `INSTALLED_APPS` in `myapp/settings.py`:
```python
INSTALLED_APPS = [
    # ... other apps
    "rest_framework.authtoken",
]
```

Run database migrations to set up DRF token tables:
```bash
python manage.py migrate
```

### 3. Require Login and Pass Token to Template
Modify `myapp/urls.py` to generate and pass a DRF token to the template:
```python
from django.contrib.auth.decorators import login_required
from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from rest_framework.authtoken.models import Token


@login_required(login_url="/admin/login/")
def client_view(request):
    token, _ = Token.objects.get_or_create(user=request.user)
    return render(
        request, "client.html", {"user": request.user, "token": token.key}
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", client_view),
]
```

### 4. Update Middleware
Update `myapp/ws.py` to use `DRFTokenAuthMiddleware` instead of `SessionAuthMiddleware`:
```python
from django.urls import path
from django_sockets.middleware import DRFTokenAuthMiddleware
from django_sockets.sockets import BaseSocketServer
from django_sockets.utils import URLRouter

# ... Keep SocketServer class definition ...


def get_ws_asgi_application():
    return DRFTokenAuthMiddleware(
        URLRouter(
            [
                path("ws/", SocketServer.as_asgi),
            ]
        )
    )
```

### 5. Update client.html Subprotocol
Modify `templates/client.html` to pass the token using the `Sec-WebSocket-Protocol` header:
```javascript
        const wsUrl = "ws://localhost:8000/ws/";
        // Pass the token inside the subprotocols list prefixing it with 'Token.'
        const websocket = new WebSocket(wsUrl, ["Token.{{ token }}"]);
```

Run the server again using Uvicorn. Authenticated users will now connect securely via token authentication.
