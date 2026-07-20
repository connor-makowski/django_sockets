from .token import BaseTokenAuthMiddleware
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)


class DRFTokenAuthMiddleware(BaseTokenAuthMiddleware):
    def __init__(self, app):
        super().__init__(app)
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
            user = self.TokenModel.objects.get(key=token).user
            if user is not None and not user.is_active:
                return None
            return user
        except Exception:
            return None
