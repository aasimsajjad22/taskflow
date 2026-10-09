from .base import *

# Always show detailed error pages on your machine.
DEBUG = True
# Hosts allowed locally. 0.0.0.0 is how Docker exposes the server.
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]
# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}
