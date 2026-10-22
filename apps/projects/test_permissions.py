# pytest.
import pytest

# Build URLs from route names.
from django.urls import reverse

# Factories.
from apps.projects.factories import ProjectFactory, TaskFactory
from apps.users.factories import UserFactory
from apps.workspaces.factories import MembershipFactory
from apps.workspaces.models import Membership

pytestmark = pytest.mark.django_db


# Returns a user with the given role in the project's workspace.
# "outsider" = a user who is not a member at all.
def user_with_role(project, role):
    workspace = project.workspace
    if role == "owner":
        return workspace.owner
    if role == "outsider":
        return UserFactory()
    # admin or member: add a new user to the workspace with that role.
    return MembershipFactory(workspace=workspace, role=role).user


# The rules from Phase 3, as a table. Each row:
# (action name, HTTP method, how to build the URL, JSON body, expected status per role).
CASES = [
    (
        "rename workspace",
        "patch",
        lambda p, t: reverse("api:workspace-detail", args=[p.workspace_id]),
        {"name": "Renamed"},
        {"owner": 200, "admin": 200, "member": 403, "outsider": 404},
    ),
    (
        "delete workspace",
        "delete",
        lambda p, t: reverse("api:workspace-detail", args=[p.workspace_id]),
        None,
        {"owner": 204, "admin": 403, "member": 403, "outsider": 404},
    ),
    (
        "archive project",
        "patch",
        lambda p, t: reverse("api:project-detail", args=[p.id]),
        {"is_archived": True},
        {"owner": 200, "admin": 200, "member": 403, "outsider": 404},
    ),
    (
        "edit task",
        "patch",
        lambda p, t: reverse("api:task-detail", args=[t.id]),
        {"title": "Edited"},
        {"owner": 200, "admin": 200, "member": 200, "outsider": 404},
    ),
    (
        "delete someone else's task",
        "delete",
        lambda p, t: reverse("api:task-detail", args=[t.id]),
        None,
        {"owner": 204, "admin": 204, "member": 403, "outsider": 404},
    ),
]
PARAMS = [
    pytest.param(method, make_url, body, role, status, id=f"{name} as {role}")
    for name, method, make_url, body, expected in CASES
    for role, status in expected.items()
]


@pytest.mark.parametrize(("method", "make_url", "body", "role", "expected"), PARAMS)
def test_permission_matrix(client_for, method, make_url, body, role, expected):
    # A project with one task. The task's reporter is the workspace OWNER,
    # so for an admin or member it is "someone else's task".
    project = ProjectFactory()
    task = TaskFactory(project=project)
    # A logged-in client for a user with the role under test.
    client = client_for(user_with_role(project, role))
    # getattr(client, "patch") == client.patch: call the right HTTP method by name.
    response = getattr(client, method)(make_url(project, task), body, format="json")
    # The status must match the table.
    assert response.status_code == expected


# The membership roles we just used must match the model's choices (a cheap safety net:
# if someone renames a role, this test points at the table above).
def test_roles_in_table_exist():
    assert {"admin", "member"} <= set(Membership.Role.values)
