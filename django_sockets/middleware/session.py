from http.cookies import SimpleCookie
from importlib import import_module
from django.conf import settings
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)


class SessionAuthMiddleware:
    def __init__(self, app):
        self.app = app
        try:
            from django.contrib.auth.models import AnonymousUser
            from django.contrib.auth import get_user_model

            self.AnonymousUser = AnonymousUser
            self.get_user_model = get_user_model
        except Exception:
            self.AnonymousUser = None
            self.get_user_model = None

    @sync_to_async
    def get_user_from_session_key(self, session_key):
        if self.get_user_model is None:
            return None
        try:
            engine = import_module(settings.SESSION_ENGINE)
            session = engine.SessionStore(session_key=session_key)
            user_id = session.get("_auth_user_id")
            if user_id:
                User = self.get_user_model()
                try:
                    user = User.objects.get(pk=user_id)
                    user.backend = session.get("_auth_user_backend")
                    return user
                except User.DoesNotExist:
                    pass
        except Exception as e:
            logger.debug(f"Error loading user from session: {e}")
        return None

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        headers = dict(scope.get("headers", []))

        # Determine the session cookie name from settings
        try:
            cookie_name = settings.SESSION_COOKIE_NAME
        except:
            cookie_name = "sessionid"

        session_key = None
        if b"cookie" in headers:
            try:
                cookie_str = headers[b"cookie"].decode()
                cookie = SimpleCookie()
                cookie.load(cookie_str)
                if cookie_name in cookie:
                    session_key = cookie[cookie_name].value
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
