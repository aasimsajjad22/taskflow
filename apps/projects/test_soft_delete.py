# pytest.
import pytest

# Build URLs from route names.
from django.urls import reverse

# Factories, models, and selectors.
from apps.projects.factories import TaskFactory
from apps.projects.models import Task
from apps.projects.selectors import workspace_dashboard
from apps.workspaces.factories import MembershipFactory

pytestmark = pytest.mark.django_db


# DELETE keeps the row, but hides it from every normal query.
def test_delete_is_soft(client_for):
    task = TaskFactory()
    client = client_for(task.project.workspace.owner)
    assert client.delete(reverse("api:task-detail", args=[task.id])).status_code == 204
    # Hidden from the default manager, the API, and the dashboard numbers...
    assert not Task.objects.filter(pk=task.pk).exists()
    assert client.get(reverse("api:task-detail", args=[task.id])).status_code == 404
    assert workspace_dashboard(workspace_id=task.project.workspace_id)["totals"]["total"] == 0
    # ...but still in the database, with a deletion time.
    assert Task.all_objects.get(pk=task.pk).deleted_at is not None


# The trash lists deleted tasks; restore brings them back.
def test_trash_and_restore(client_for):
    task = TaskFactory()
    client = client_for(task.project.workspace.owner)
    client.delete(reverse("api:task-detail", args=[task.id]))

    trash = client.get(reverse("api:task-trash")).json()
    assert [t["id"] for t in trash["results"]] == [task.id]

    response = client.post(reverse("api:task-restore", args=[task.id]))
    assert response.status_code == 200
    assert Task.objects.filter(pk=task.pk).exists()
    # Not in the trash anymore: a second restore finds nothing.
    assert client.post(reverse("api:task-restore", args=[task.id])).status_code == 404


# Restoring follows the delete rule: a plain member can't restore someone else's task.
def test_member_cannot_restore_others_task(client_for):
    task = TaskFactory()
    workspace = task.project.workspace
    client_for(workspace.owner).delete(reverse("api:task-detail", args=[task.id]))
    member = MembershipFactory(workspace=workspace).user
    assert client_for(member).post(reverse("api:task-restore", args=[task.id])).status_code == 403
