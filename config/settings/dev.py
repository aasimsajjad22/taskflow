from .base import *

# Always show detailed error pages on your machine.
DEBUG = True
# Hosts allowed locally. 0.0.0.0 is how Docker exposes the server.
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]
# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

INSTALLED_APPS = [*INSTALLED_APPS, "django_extensions", "debug_toolbar"]

MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE]

DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG}

CELERY_WORKER_POOL = "threads"

# Emails go to Mailpit in development (configured in base.py through EMAIL_HOST / EMAIL_PORT).
