# A WebSocket client: connect, then wait for live events (Phase 10 demo).
import asyncio
import json
import os

import django
import websockets

# Use the project's dev settings, so we can make a token like the login endpoint does.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from rest_framework_simplejwt.tokens import AccessToken  # noqa: E402

from apps.users.models import User  # noqa: E402
from apps.workspaces.models import Workspace  # noqa: E402

# The demo owner (Phase 4's seed_demo) and their workspace.
owner = User.objects.get(email="demo-owner@example.com")
workspace = Workspace.objects.filter(owner=owner).first()
token = str(AccessToken.for_user(owner))


async def main():
    url = f"ws://localhost:8000/ws/workspaces/{workspace.id}/?token={token}"
    # origin=...: a browser sends this header itself; our Origin check needs it.
    async with websockets.connect(url, origin="http://localhost") as sock:
        print("connected - now change a task in workspace", workspace.id)
        while True:
            print("received:", json.loads(await sock.recv()))


asyncio.run(main())
