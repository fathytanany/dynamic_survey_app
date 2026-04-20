from .base import *  # noqa: F401, F403

DEBUG = True

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405

MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405

INTERNAL_IPS = ["127.0.0.1"]

# Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

# Use console email in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Looser DB SSL in development
DATABASES["default"]["OPTIONS"]["sslmode"] = "disable"  # noqa: F405
