from http.cookies import SimpleCookie
from importlib import import_module
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)


class SessionAuthMiddleware:
    """
    Middleware that authenticates a Django user from the session cookie in
    the WebSocket connection headers.
    """

    __slots__ = (
        "app",
        "select_related",
        "AnonymousUser",
        "get_user_model",
        "settings",
        "_cookie_name",
    )

    def __init__(self, app, select_related=None):
        """
        Initialize the Session Auth Middleware

        Requires:

        - app: ASGI application = The downstream ASGI application

        Optional:

        - select_related: list[str] = Model fields to pass to `select_related()`
            when querying the user model from the database session ID
        """
        self.app = app
        self.select_related = select_related
        try:
            from django.contrib.auth.models import AnonymousUser
            from django.contrib.auth import get_user_model
            from django.conf import settings

            self.AnonymousUser = AnonymousUser
            self.get_user_model = get_user_model
            self.settings = settings
            self._cookie_name = getattr(
                settings, "SESSION_COOKIE_NAME", "sessionid"
            )
        except Exception:
            self.AnonymousUser = None
            self.get_user_model = None
            self.settings = None
            self._cookie_name = "sessionid"

    @sync_to_async
    def get_user_from_session_key(self, session_key):
        if self.get_user_model is None or self.settings is None:
            return None
        try:
            engine = import_module(self.settings.SESSION_ENGINE)
            session = engine.SessionStore(session_key=session_key)
            user_id = session.get("_auth_user_id")
            if user_id:
                User = self.get_user_model()
                qs = User.objects
                if self.select_related:
                    qs = qs.select_related(*self.select_related)
                user = qs.filter(pk=user_id).first()
                if user is not None:
                    user.backend = session.get("_auth_user_backend")
                    return user
        except Exception as e:
            logger.debug(f"Error loading user from session: {e}")
        return None

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        raw_headers = scope.get("headers", [])
        cookie_name = self._cookie_name

        session_key = None
        for k, v in raw_headers:
            if k.lower() == b"cookie":
                cookie_str = v.decode("latin1", errors="ignore")
                if cookie_name in cookie_str:
                    try:
                        cookie = SimpleCookie()
                        cookie.load(cookie_str)
                        if cookie_name in cookie:
                            session_key = cookie[cookie_name].value
                            break
                    except Exception as e:
                        logger.debug(f"Error parsing cookies: {e}")

        user = None
        if session_key:
            user = await self.get_user_from_session_key(session_key)

        if user is None:
            if self.AnonymousUser is not None:
                user = self.AnonymousUser()

        scope["user"] = user
        return await self.app(scope, receive, send)
