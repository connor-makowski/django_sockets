from urllib.parse import parse_qs
import logging

logger = logging.getLogger(__name__)


class BaseTokenAuthMiddleware:
    """
    Base middleware class for token-based WebSocket authentication.

    Extracts tokens from either:
    1. Query string parameters: `?token=<key>` or `?auth_token=<key>`
    2. Subprotocol headers: `Sec-WebSocket-Protocol: Token.<key>`

    Subclasses must implement `get_user(self, token)` to resolve the user.
    """

    __slots__ = ("app", "AnonymousUser", "__dict__")

    def __init__(self, app):
        """
        Initialize the Base Token Auth Middleware

        Requires:

        - app: ASGI application = The downstream ASGI application
        """
        self.app = app
        try:
            from django.contrib.auth.models import AnonymousUser

            self.AnonymousUser = AnonymousUser
        except Exception:
            self.AnonymousUser = None

    def get_anonymous_user_obj(self):
        if self.AnonymousUser is not None:
            return self.AnonymousUser()
        logger.log(
            logging.ERROR,
            "Unable to get AnonymousUser object. Check to make sure Django is properly installed and configured before using this middleware.",
        )
        return None

    async def get_user(self, token):
        raise NotImplementedError(
            "You must implement the get_user method when extending BaseTokenAuthMiddleware"
        )

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        raw_headers = scope.get("headers", [])
        token = None
        user_obj = None

        # 1. Check if token is passed in query string (?token=... or ?auth_token=...)
        raw_query = scope.get("query_string", b"")
        if raw_query:
            try:
                query_str = (
                    raw_query.decode("utf-8")
                    if isinstance(raw_query, bytes)
                    else raw_query
                )
                params = parse_qs(query_str)
                for q_key in ("token", "auth_token"):
                    val = params.get(q_key)
                    if val and val[0].strip():
                        token = val[0].strip()
                        break
            except Exception as e:
                logger.debug(f"Error parsing query string token: {e}")

        # 2. Check if token is passed in Sec-WebSocket-Protocol headers (Token.<token>)
        if not token:
            for k, v in raw_headers:
                if k.lower() == b"sec-websocket-protocol":
                    try:
                        protocols = [
                            p.strip()
                            for p in v.decode("utf-8", errors="ignore").split(
                                ","
                            )
                        ]
                        token_protocols = [
                            i for i in protocols if i.startswith("Token.")
                        ]
                        if len(token_protocols) > 0:
                            scope["__chosen_subprotocol__"] = token_protocols[0]
                            token = token_protocols[0][len("Token.") :].strip()
                            break
                    except Exception as e:
                        logger.debug(
                            f"Error parsing subprotocol header token: {e}"
                        )

        # Update the scope with the user object
        if token is not None:
            try:
                user_obj = await self.get_user(token)
            except Exception:
                pass
        if user_obj is None:
            user_obj = self.get_anonymous_user_obj()
        scope["user"] = user_obj
        return await self.app(scope, receive, send)
