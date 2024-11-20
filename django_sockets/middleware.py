from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)

# Django Channels Middleware (To be importable from django_sockets)
# Do not remove these imports
from channels.auth import AuthMiddlewareStack


def get_anonymous_user_obj():
    try:
        return AnonymousUser()
    except:
        pass
    try:
        from django.contrib.auth.models import AnonymousUser

        return AnonymousUser()
    except:
        pass
    logger.log(
        logging.ERROR,
        "Unable to get AnonymousUser object. Check to make sure Django is properly installed before using this middleware.",
    )
    return None


def get_drf_token_obj():
    try:
        return Token
    except:
        pass
    try:
        from rest_framework.authtoken.models import Token

        return Token
    except:
        pass
    logger.log(
        logging.ERROR,
        "Unable to get Token object. Check to make sure Django Rest Framework is properly installed before using this middleware.",
    )
    return None


@database_sync_to_async
def get_drf_user(user_token):
    if user_token is not None:
        try:
            token = get_drf_token_obj().objects.get(key=user_token)
            return token.user
        except:
            pass
    return get_anonymous_user_obj()


def get_query_key_with_priority(
    query_string: str, keys: list = list(), default=None
):
    try:
        if isinstance(keys, str):
            keys = [keys]
        query_dict = dict(
            (x.split("=") for x in query_string.decode().split("&"))
        )
        for key in keys:
            if key in query_dict:
                return query_dict[key]
    except:
        pass
    return default


class DRFTokenAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        headers = dict(scope["headers"])
        token = None
        if b"sec-websocket-protocol" in headers:
            protocols = headers[b"sec-websocket-protocol"].decode().split(", ")
            token_protocols = [i for i in protocols if i.startswith("Token.")]
            if len(token_protocols) > 0:
                scope["__chosen_subprotocol__"] = token_protocols[0]
                token = token_protocols[0].replace("Token.", "")
        if token is None:
            token = get_query_key_with_priority(
                scope["query_string"], ["token", "Token", "user_token"]
            )
        # Update the scope with the user object
        scope["user"] = await get_drf_user(token)
        return await self.app(scope, receive, send)
