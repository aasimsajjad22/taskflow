# database_sync_to_async: run ORM code from async code.
from channels.db import database_sync_to_async

# A consumer = Channels' version of a view, for WebSockets. "Json" = it sends/receives JSON.
from channels.generic.websocket import AsyncJsonWebsocketConsumer

# The Membership model, for the "is this user a member?" check.
from apps.workspaces.models import Membership

# The group name helper.
from .events import workspace_group


# ws://.../ws/workspaces/<id>/?token=... : live events of one workspace.
# Like a view, but the connection stays OPEN: the server can push messages at any time.
class WorkspaceConsumer(AsyncJsonWebsocketConsumer):
    # Runs when a client connects (the WebSocket "handshake").
    async def connect(self):
        # Set by JWTAuthMiddleware.
        user = self.scope["user"]
        # No valid token: refuse. 4401 = our own code ("not authenticated"; 4000-4999 are free
        # for apps to use). Closing BEFORE accept() refuses the handshake itself.
        if not user.is_authenticated:
            await self.close(code=4401)
            return
        # The workspace id from the URL (see routing.py).
        self.workspace_id = int(self.scope["url_route"]["kwargs"]["workspace_id"])
        # Not a member: refuse (4403 = "forbidden"). Same rule as the HTTP API.
        if not await self.is_member(user):
            await self.close(code=4403)
            return
        # Join the workspace's group, so group_send() messages reach this connection.
        self.group = workspace_group(self.workspace_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        # Accept the connection.
        await self.accept()

    # Runs when the connection closes (client left, network lost...).
    async def disconnect(self, code):
        # Leave the group (only if we joined it: refused connections never did).
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    # Handles messages of type "workspace.event" (sent by publish_workspace_event).
    # The dot in the type becomes an underscore in the method name.
    async def workspace_event(self, message):
        # Push it to the browser as JSON, e.g. {"event": "task.updated", "task_id": 42, ...}.
        await self.send_json({"event": message["event"], **message["data"]})

    # The membership check, as ORM code run in a thread.
    @database_sync_to_async
    def is_member(self, user) -> bool:
        return Membership.objects.filter(user=user, workspace_id=self.workspace_id).exists()
