# pytest.
import pytest

# async_to_sync: run an async test scenario from a normal test function (Phase 6).
from asgiref.sync import async_to_sync

# database_sync_to_async: call our (sync) services from the async scenario.
from channels.db import database_sync_to_async

# Channels' test client for WebSockets: connect, send, receive, disconnect. No server needed.
from channels.testing import WebsocketCommunicator

# A real access token, made the same way the login endpoint makes it (Phase 3).
from rest_framework_simplejwt.tokens import AccessToken

# Factories and services.
from apps.projects.factories import TaskFactory
from apps.projects.services import task_update
from apps.users.factories import UserFactory

# The full ASGI app: Origin check -> JWT middleware -> router -> consumer.
from config.asgi import application

# transaction=True: the consumer checks membership in ANOTHER thread (database_sync_to_async).
# A normal test keeps its data in an open transaction that other threads can't see, so here
# the test data must really be committed (and the tables are emptied after each test).
pytestmark = pytest.mark.django_db(transaction=True)


# A test client for one workspace's socket. The Origin header must match ALLOWED_HOSTS
# ("testserver" is always allowed in tests), or AllowedHostsOriginValidator refuses us.
def socket(workspace_id, token=None):
    path = f"/ws/workspaces/{workspace_id}/" + (f"?token={token}" if token else "")
    return WebsocketCommunicator(application, path, headers=[(b"origin", b"http://testserver")])


# The access token for a user, as a string.
def token_for(user):
    return str(AccessToken.for_user(user))


# No token, a broken token, or a non-member: the handshake is refused with our close code.
@pytest.mark.parametrize(
    ("who", "code"), [("nobody", 4401), ("bad token", 4401), ("outsider", 4403)]
)
def test_connection_is_refused(who, code):
    task = TaskFactory()
    token = {"nobody": None, "bad token": "not-a-jwt", "outsider": token_for(UserFactory())}[who]

    async def scenario():
        communicator = socket(task.project.workspace_id, token)
        # connect() returns (False, close_code) when the server refuses.
        connected, close_code = await communicator.connect()
        return connected, close_code

    assert async_to_sync(scenario)() == (False, code)


# A member connects; when a task changes, the event arrives on the socket.
def test_member_receives_task_events():
    task = TaskFactory()
    owner = task.project.workspace.owner

    async def scenario():
        communicator = socket(task.project.workspace_id, token_for(owner))
        connected, _ = await communicator.connect()
        assert connected
        # Change the task through the normal service (it commits: transaction=True above).
        await database_sync_to_async(task_update)(task=task, data={"status": "done"}, actor=owner)
        # The event published after the commit reaches this socket.
        event = await communicator.receive_json_from(timeout=2)
        await communicator.disconnect()
        return event

    assert async_to_sync(scenario)() == {
        "event": "task.updated",
        "target_type": "task",
        "target_id": task.id,
    }


# A socket from ANOTHER website's page is refused (cross-site WebSocket hijacking).
def test_foreign_origin_is_refused():
    task = TaskFactory()

    async def scenario():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/workspaces/{task.project.workspace_id}/?token={token_for(task.reporter)}",
            headers=[(b"origin", b"https://evil.example")],
        )
        connected, _ = await communicator.connect()
        return connected

    assert async_to_sync(scenario)() is False
