# Settings for production. Security is turned ON here.
# Start from the base settings.
from .base import *

# Never show debug pages in production. They leak secrets and code.
DEBUG = False
# Our app will sit behind a proxy/load balancer that handles HTTPS.
# This tells Django to trust the proxy's header that says "the original request was HTTPS".
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Redirect all HTTP requests to HTTPS. Can be turned off by env if the proxy does it.
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
# Only send the session cookie over HTTPS.
SESSION_COOKIE_SECURE = True
# Only send the CSRF cookie over HTTPS.
CSRF_COOKIE_SECURE = True
# HSTS: tell browsers "only use HTTPS for this site" for N seconds.
# Start small (60). Increase to 31536000 (1 year) once you're sure HTTPS works.
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60)
# Apply HSTS to subdomains too.
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# Stop browsers from guessing file types (blocks some attacks).
SECURE_CONTENT_TYPE_NOSNIFF = True
# Origins allowed to send POST forms, e.g. "https://app.taskflow.com". From env.
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
