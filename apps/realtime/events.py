# logging: real-time messages are "best effort": if sending fails, we log it and move on.
import logging

# async_to_sync: call the channel layer's async functions from our normal (sync) code.
from asgiref.sync import async_to_sync

# get_channel_layer: the message bus between server processes (Redis; in-memory in tests).
from channels.layers import get_channel_layer

# transaction.on_commit: send only after the change is really saved (Phase 5 lesson).
from django.db import transaction

logger = logging.getLogger(__name__)


def workspace_group(workspace_id: int) -> str:
    return f"workspace-{workspace_id}"


def publish_workspace_event(*, workspace_id: int, event: str, data: dict) -> None:
    def send():
        try:
            async_to_sync(get_channel_layer().group_send)(
                workspace_group(workspace_id),
                {"type": "workspace.event", "event": event, "data": data},
            )
        except Exception:
            logger.warning("Could not publish %s for workspace %s", event, workspace_id)

    transaction.on_commit(send)
