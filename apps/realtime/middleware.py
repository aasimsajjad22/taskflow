# parse_qs: read the "?token=..." part of the WebSocket URL.
from urllib.parse import parse_qs

# database_sync_to_async: run normal (sync) ORM code from async code, in a thread (Phase 6).
from channels.db import database_sync_to_async

# AnonymousUser: "nobody is logged in".
from django.contrib.auth.models import AnonymousUser

# The errors that SimpleJWT raises for bad tokens and unknown users.
from rest_framework.exceptions import AuthenticationFailed

# SimpleJWT's normal authentication class: we reuse its token checks (Phase 3).
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


# Check the token and load the user. The same checks as the HTTP API: signature, expiry,
# token type ("access" only), and an active user.
@database_sync_to_async
def get_user_from_token(raw_token: str):
    authentication = JWTAuthentication()
    try:
        validated_token = authentication.get_validated_token(raw_token)
        return authentication.get_user(validated_token)
    except (InvalidToken, AuthenticationFailed):
        # Any problem: treat the connection as anonymous. The consumer will refuse it.
        return AnonymousUser()


# ASGI middleware: runs once when a WebSocket connects, before the consumer.
# Browsers can't send an "Authorization" header with a WebSocket, so the access token comes
# in the URL: ws://.../ws/workspaces/3/?token=<access token>
class JWTAuthMiddleware:
    # "inner" = the next layer (the URL router with our consumers).
    def __init__(self, inner):
        self.inner = inner

    # Called for every new connection. scope = the connection's details (like request.META).
    async def __call__(self, scope, receive, send):
        # The query string arrives as bytes, e.g. b"token=eyJ...". parse_qs -> {"token": [...]}.
        query = parse_qs(scope.get("query_string", b"").decode())
        token = query.get("token", [None])[0]
        # Put the user in the scope (a COPY: scopes are shared, never change them in place).
        user = await get_user_from_token(token) if token else AnonymousUser()
        scope = {**scope, "user": user}
        # Continue to the router and the consumer.
        return await self.inner(scope, receive, send)
