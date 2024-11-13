from .utils import database_sync_to_async
import logging

logger = logging.getLogger(__name__)


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


def get_query_arg(query_string, arg, default=None):
    try:
        return (
            dict((x.split("=") for x in query_string.decode().split("&")))
        ).get(arg, default)
    except:
        return None


class DRFTokenAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        scope["user"] = await get_drf_user(
            get_query_arg(scope["query_string"], "user_token")
        )
        return await self.app(scope, receive, send)
