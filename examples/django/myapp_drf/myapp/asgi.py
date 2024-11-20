"""
ASGI config for myapp project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

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