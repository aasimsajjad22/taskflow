from .base import *

# Tests never need debug pages.
DEBUG = False
# Use a very fast (and weak) password hasher.
# Real hashers are slow ON PURPOSE, which makes tests with many users slow.
# NEVER use this outside tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        name: "10000/minute" for name in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    },
}
# Use an in-memory cache in tests instead of Redis.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Phase 10: tests use an in-memory channel layer (no Redis needed, like the cache above).
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Phase 10: fixed hosts for tests. The WebSocket Origin check (config/asgi.py) reads
# ALLOWED_HOSTS once, at import time, before Django's test setup adds "testserver" itself.
# Setting it here also makes tests independent of a local .env file (CI has none).
ALLOWED_HOSTS = ["testserver", "localhost"]
