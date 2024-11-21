from .token import BaseTokenAuthMiddleware
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)

# Safe import of DRF Token model
# This allows us to avoid requiring Django Rest Framework to be installed
try:
    from rest_framework.authtoken.models import Token

    def get_drf_token_user(token):
        return Token.objects.get(key=token).user

except:

    def get_drf_token_user(token):
        logger.log(
            logging.ERROR,
            "Unable to import DRF Token model. Make sure you have Django Rest Framework installed and properly configured before using this middleware.",
        )
        return None


class DRFTokenAuthMiddleware(BaseTokenAuthMiddleware):
    @database_sync_to_async
    def get_user(self, token):
        return get_drf_token_user(token)
