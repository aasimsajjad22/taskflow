# path(): the same URL patterns as in urls.py.
from django.urls import path

# The consumer.
from .consumers import WorkspaceConsumer

# WebSocket URLs (like urlpatterns, but for WebSocket connections).
# as_asgi(): like as_view() for views; it creates one consumer instance per connection.
websocket_urlpatterns = [
    path("ws/workspaces/<int:workspace_id>/", WorkspaceConsumer.as_asgi()),
]
