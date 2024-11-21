from django.http import QueryDict
import logging

logger = logging.getLogger(__name__)

# Safe import of AnonymousUser
# This allows us to avoid requiring Django to be setup / configured for non Django projects.
try:
    from django.contrib.auth.models import AnonymousUser

    def get_anonymous_user_obj():
        return AnonymousUser()

except:

    def get_anonymous_user_obj():
        logger.log(
            logging.ERROR,
            "Unable to get AnonymousUser object. Check to make sure Django is properly installed and configured before using this middleware.",
        )
        return None


class BaseTokenAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def get_user(self, token):
        raise NotImplementedError(
            "You must implement the get_user method when extending BaseTokenAuthMiddleware"
        )

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        headers = dict(scope["headers"])
        token = None
        user_obj = None
        # Handle the case where the token is passed in the headers
        if b"sec-websocket-protocol" in headers:
            protocols = headers[b"sec-websocket-protocol"].decode().split(", ")
            token_protocols = [i for i in protocols if i.startswith("Token.")]
            if len(token_protocols) > 0:
                scope["__chosen_subprotocol__"] = token_protocols[0]
                token = token_protocols[0].replace("Token.", "")
        # Handle the case where the token is passed in the query string
        if token is None:
            query_params = QueryDict(scope["query_string"].decode())
            for key in ["token", "Token", "user_token"]:
                if key in query_params:
                    token = query_params.get(key)
                    break
        # Update the scope with the user object
        if token is not None:
            try:
                user_obj = await self.get_user(token)
            except:
                pass
        if user_obj is None:
            user_obj = get_anonymous_user_obj()
        scope["user"] = user_obj
        return await self.app(scope, receive, send)
