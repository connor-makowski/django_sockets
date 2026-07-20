import subprocess
import sys


def test_django_import_order():
    # Test that importing middleware in a clean environment where Django is not
    # initialized yet, then setting up Django, and then using the middleware
    # does not fail and correctly resolves AnonymousUser.
    code = """
import os
import django
from django.conf import settings

# 1. Import middlewares BEFORE setting up Django (simulate bad asgi import order)
from django_sockets.middleware import SessionAuthMiddleware, DRFTokenAuthMiddleware

# 2. Setup Django afterwards
if not settings.configured:
    settings.configure(
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        SECRET_KEY="test-secret-key",
    )
    django.setup()

# 3. Instantiate middleware and verify they work and AnonymousUser is correctly resolved
from django.contrib.auth.models import AnonymousUser

async def mock_app(scope, receive, send):
    assert isinstance(scope["user"], AnonymousUser)
    print("SUCCESS")

session_mw = SessionAuthMiddleware(mock_app)
drf_mw = DRFTokenAuthMiddleware(mock_app)

# Mock scope to execute middleware __call__
import asyncio

scope = {"headers": {}, "query_string": b""}
asyncio.run(session_mw(scope, None, None))
asyncio.run(drf_mw(scope, None, None))
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert (
        result.returncode == 0
    ), f"Import order test failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    print("09_django_import_order.py: PASS")


if __name__ == "__main__":
    test_django_import_order()
