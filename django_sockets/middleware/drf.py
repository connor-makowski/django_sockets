from .token import BaseTokenAuthMiddleware
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)


class DRFTokenAuthMiddleware(BaseTokenAuthMiddleware):
    """
    Middleware that authenticates a Django Rest Framework (DRF) Token from
    query string parameters or the Sec-WebSocket-Protocol header.

    Token resolution checks:
    1. Query parameters: `?token=<key>` or `?auth_token=<key>`
    2. WebSocket subprotocols: `Sec-WebSocket-Protocol: Token.<key>`
    """

    __slots__ = ("select_related", "TokenModel")

    def __init__(self, app, select_related=None):
        """
        Initialize the DRF Token Auth Middleware

        Requires:

        - app: ASGI application = The downstream ASGI application

        Optional:

        - select_related: list[str] = Model fields to pass to `select_related()`
            when querying the token model (default: `["user"]`)
        """
        super().__init__(app)
        self.select_related = select_related or ["user"]
        try:
            from rest_framework.authtoken.models import Token

            self.TokenModel = Token
        except Exception:
            self.TokenModel = None

    @sync_to_async
    def get_user(self, token):
        if self.TokenModel is None:
            logger.log(
                logging.ERROR,
                "Unable to import DRF Token model. Make sure you have Django Rest Framework installed and properly configured before using this middleware.",
            )
            return None
        try:
            qs = self.TokenModel.objects
            if self.select_related:
                qs = qs.select_related(*self.select_related)
            token_obj = qs.filter(key=token).first()
            if token_obj and token_obj.user and token_obj.user.is_active:
                return token_obj.user
            return None
        except Exception:
            return None
