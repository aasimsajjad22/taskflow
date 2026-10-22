# pytest: fixtures, marks, parametrize, raises.
import pytest

# The error our services raise.
from django.core.exceptions import ValidationError

# Factories (test data) and the code under test.
from apps.projects.factories import ProjectFactory, TaskFactory
from apps.projects.models import Task
from apps.projects.services import task_claim, task_create, task_update
from apps.workspaces.factories import MembershipFactory

# Every test in this file uses the database.
pytestmark = pytest.mark.django_db


# Rule (Phase 2): no new tasks in an archived project.
def test_cannot_create_task_in_archived_project():
    # One line builds a whole chain: project -> workspace -> owner (+ owner membership).
    project = ProjectFactory(is_archived=True)
    # The service must refuse, with an error on the "project" field.
    with pytest.raises(ValidationError) as error:
        task_create(project=project, title="Too late", reporter=project.workspace.owner)
    # .value is the raised exception; message_dict = {"field": ["message"]}.
    assert "project" in error.value.message_dict


# Rule (Phase 2): completed_at follows the status. One test, several cases:
# each tuple is (start status, new status, should completed_at be set afterwards?).
@pytest.mark.parametrize(
    ("start", "new", "completed"),
    [
        (Task.Status.TODO, Task.Status.DONE, True),
        (Task.Status.IN_PROGRESS, Task.Status.DONE, True),
        (Task.Status.TODO, Task.Status.IN_PROGRESS, False),
    ],
)
def test_completed_at_follows_status(start, new, completed):
    # A task in the starting status.
    task = TaskFactory(status=start)
    # Change the status through the service.
    task = task_update(task=task, data={"status": new})
    # "is not None" is True when a completion time was set.
    assert (task.completed_at is not None) is completed


# Reopening a done task clears completed_at again.
def test_reopening_clears_completed_at():
    task = task_update(task=TaskFactory(), data={"status": Task.Status.DONE})
    task = task_update(task=task, data={"status": Task.Status.TODO})
    assert task.completed_at is None


# Rule (Phase 4): only open, unassigned tasks can be claimed.
@pytest.mark.parametrize(
    ("status", "already_assigned"),
    [(Task.Status.DONE, False), (Task.Status.TODO, True)],
    # ids: readable names in the test output instead of "status0-already_assigned0".
    ids=["done task", "already assigned"],
)
def test_claim_is_refused(status, already_assigned):
    task = TaskFactory(status=status)
    # A second member of the same workspace.
    member = MembershipFactory(workspace=task.project.workspace).user
    # Optionally give the task to the owner first.
    if already_assigned:
        task.assignee = task.project.workspace.owner
        task.save()
    # Claiming must fail with an error on "task".
    with pytest.raises(ValidationError) as error:
        task_claim(task_id=task.id, user=member)
    assert "task" in error.value.message_dict


# A successful claim assigns the task to the user.
def test_claim_assigns_task():
    task = TaskFactory()
    member = MembershipFactory(workspace=task.project.workspace).user
    task = task_claim(task_id=task.id, user=member)
    assert task.assignee == member
