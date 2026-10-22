# ASGI entry point (Phase 6, extended in Phase 10). ASGI servers (daphne, uvicorn) load
# "application" from here. It routes each connection by its type: HTTP or WebSocket.

# os: to set the default settings module.
import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

# get_asgi_application: Django's normal HTTP handling, as an ASGI app.
from django.core.asgi import get_asgi_application

from apps.realtime.middleware import JWTAuthMiddleware
from apps.realtime.routing import websocket_urlpatterns

# Production settings unless the environment says otherwise (Phase 1).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

# Start Django FIRST (loads settings and apps). Code that uses models (our consumers,
# middleware) may only be imported AFTER this line, hence the "noqa: E402" below.
django_asgi_app = get_asgi_application()

# The app the server runs.
application = ProtocolTypeRouter(
    {
        # Normal HTTP requests: Django, exactly as before.
        "http": django_asgi_app,
        # WebSockets: check the Origin -> log in with the token -> route to a consumer.
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
        ),
    }
)
