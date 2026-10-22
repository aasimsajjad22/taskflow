# pytest.
import pytest

# Build URLs from route names.
from django.urls import reverse

# Factories, models, and services.
from apps.audit.models import AuditLog
from apps.projects.factories import TaskFactory
from apps.projects.models import Task
from apps.projects.services import task_bulk_update_status, task_update
from apps.workspaces.factories import MembershipFactory

pytestmark = pytest.mark.django_db


# Only the fields whose value really changed are logged, including service side effects.
def test_update_logs_only_real_changes():
    task = TaskFactory(title="Same title")
    owner = task.project.workspace.owner
    # The title is sent but NOT changed; the status is changed.
    task_update(task=task, data={"title": "Same title", "status": "done"}, actor=owner)
    log = AuditLog.objects.get(action="task.updated")
    # completed_at was set by the service's own rule, and the snapshot caught it too.
    assert set(log.changes) == {"status", "completed_at"}
    assert log.changes["status"] == ["todo", "done"]
    assert log.actor == owner


# No real change = no log row (an empty PATCH must not fill the log).
def test_no_change_no_log():
    task = TaskFactory(title="Same")
    task_update(task=task, data={"title": "Same"}, actor=task.project.workspace.owner)
    assert not AuditLog.objects.exists()


# Bulk: one row per task whose status really changed, written with ONE INSERT.
def test_bulk_logs_each_changed_task(django_assert_max_num_queries):
    first = TaskFactory()
    project = first.project
    done_already = TaskFactory(project=project, status=Task.Status.DONE)
    owner = project.workspace.owner
    ids = [first.id, done_already.id]
    # A fixed number of queries, whatever the number of tasks (no query per task).
    with django_assert_max_num_queries(8):
        task_bulk_update_status(user=owner, task_ids=ids, status=Task.Status.DONE)
    # The already-done task didn't change, so it has no row.
    assert list(AuditLog.objects.values_list("target_id", flat=True)) == [first.id]


# The log shows everyone's actions: owners and admins only.
@pytest.mark.parametrize(("role", "expected"), [("admin", 200), ("member", 403)])
def test_only_managers_read_the_log(client_for, role, expected):
    task = TaskFactory()
    user = MembershipFactory(workspace=task.project.workspace, role=role).user
    url = reverse("api:workspace-audit-log", args=[task.project.workspace_id])
    assert client_for(user).get(url).status_code == expected


# Adding a member through the API records who added whom.
def test_member_added_is_logged(client_for):
    task = TaskFactory()
    workspace = task.project.workspace
    new_user = MembershipFactory().user
    client_for(workspace.owner).post(
        reverse("api:workspace-members", args=[workspace.id]),
        {"email": new_user.email},
        format="json",
    )
    log = AuditLog.objects.get(action="member.added")
    assert log.actor == workspace.owner
    assert log.changes == {"user": [None, new_user.email], "role": [None, "member"]}
