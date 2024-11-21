# Django Channels Middleware (To be importable from django_sockets)
# Do not remove these imports
from channels.auth import AuthMiddlewareStack

from .token import BaseTokenAuthMiddleware
from .drf import DRFTokenAuthMiddleware

# Create alias for the AuthMiddlewareStack for consistent naming
SessionAuthMiddleware = AuthMiddlewareStack
