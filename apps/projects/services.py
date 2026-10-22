from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import audit_diff, audit_record
from apps.projects.cache import bump_workspace_cache_version
from apps.projects.models import Comment, Project, Task, TaskExport
from apps.projects.tasks import notify_task_assigned, run_task_export
from apps.workspaces.models import Membership
from apps.workspaces.selectors import workspace_ids_for_user

# Fields whose changes we record in the audit log (assignee_id = the plain id column).
TASK_AUDIT_FIELDS = [
    "title",
    "description",
    "status",
    "priority",
    "assignee_id",
    "due_date",
    "completed_at",
]


def create_project(*, workspace, name: str, key: str, created_by, description: str = "") -> Project:

    key = key.upper()
    if Project.objects.filter(workspace=workspace, key=key).exists():
        raise ValidationError({"key": "Project already exists"})

    return Project.objects.create(
        workspace=workspace,
        name=name,
        key=key,
        description=description,
        created_by=created_by,
    )


def project_update(*, project: Project, data: dict) -> Project:
    changed = _apply_updates(
        instance=project, data=data, allowed_fields=["name", "is_archived", "description"]
    )

    if changed:
        project.save(update_fields=[*changed, "updated_at"])

    return project


def task_create(
    *,
    project: Project,
    title: str,
    reporter,
    description: str = "",
    priority: int = Task.Priority.MEDIUM,
    assignee=None,
    due_date=None,
) -> Task:
    if project.is_archived:
        raise ValidationError({"project": "You cannot add tasks to an archived project."})

    _validate_assignee(project=project, assignee=assignee)

    task = Task.objects.create(
        project=project,
        title=title,
        description=description,
        priority=priority,
        assignee=assignee,
        reporter=reporter,
        due_date=due_date,
    )

    if task.assignee is not None:
        _notify_assignee_after_commit(task=task)

    _invalidate_workspace_cache(project.workspace_id)

    audit_record(
        workspace_id=project.workspace_id, actor=reporter, action="task.created", target=task
    )
    return task


def task_update(*, task: Task, data: dict, actor=None) -> Task:
    if "assignee" in data:
        _validate_assignee(project=task.project, assignee=data["assignee"])

    old_status = task.status
    old_assignee_id = task.assignee_id

    before = {field: getattr(task, field) for field in TASK_AUDIT_FIELDS}

    changed = _apply_updates(
        instance=task,
        data=data,
        allowed_fields=["title", "description", "status", "priority", "assignee", "due_date"],
    )

    if task.status == Task.Status.DONE and old_status != task.Status.DONE:
        task.completed_at = timezone.now()
        changed.append("completed_at")
    elif task.status != Task.Status.DONE and old_status == Task.Status.DONE:
        task.completed_at = None
        changed.append("completed_at")

    if changed:
        task.save(update_fields=[*changed, "updated_at"])
        _invalidate_workspace_cache(task.project.workspace_id)

        after = {field: getattr(task, field) for field in TASK_AUDIT_FIELDS}
        diff = audit_diff(before, after)
        if diff:
            audit_record(
                workspace_id=task.project.workspace_id,
                actor=actor,
                action="task.updated",
                target=task,
                changes=diff,
            )

    if task.assignee_id is not None and task.assignee_id != old_assignee_id:
        _notify_assignee_after_commit(task=task)

    return task


def comment_create(*, task: Task, author, body: str) -> Comment:
    return Comment.objects.create(
        task=task,
        author=author,
        body=body,
    )


@transaction.atomic
def task_claim(*, task_id: int, user) -> Task:
    task = Task.objects.select_for_update().get(pk=task_id)

    if task.status == Task.Status.DONE:
        raise ValidationError({"task": "This task is already done."})

    if task.assignee_id is not None:
        raise ValidationError({"task": "This task is already assigned to someone."})

    _validate_assignee(project=task.project, assignee=user)

    task.assignee = user
    task.save(update_fields=["assignee", "updated_at"])

    _invalidate_workspace_cache(task.project.workspace_id)

    audit_record(
        workspace_id=task.project.workspace_id,
        actor=user,
        action="task.claimed",
        target=task,
        changes={"assignee_id": [None, user.pk]},
    )

    # The lock is released when the transaction ends (when this function returns).
    return task


# Change the status of many tasks with ONE UPDATE query.
# atomic: the UPDATE and its audit rows are saved together, or not at all.
@transaction.atomic
def task_bulk_update_status(*, user, task_ids: list[int], status: str) -> int:
    # Remove duplicate ids: [1, 1, 2] -> {1, 2}.
    unique_ids = set(task_ids)
    # Only tasks in the user's workspaces. This is our data-scoping rule again:
    # never trust ids from the client.
    tasks = Task.objects.filter(
        pk__in=unique_ids, project__workspace_id__in=workspace_ids_for_user(user=user)
    )
    # Rule: every id must be a task the user can see. Otherwise refuse everything.
    if tasks.count() != len(unique_ids):
        raise ValidationError({"task_ids": "Some tasks don't exist or you can't access them."})

    # Read the tasks whose status WILL change, BEFORE the UPDATE. Afterwards every task has
    # the new status, so this query would find nothing (and the log would stay empty).
    old_rows = list(
        tasks.exclude(status=status).values("id", "title", "status", "project__workspace_id")
    )

    # The current time, for updated_at and completed_at.
    now = timezone.now()
    # update() runs ONE "UPDATE ... WHERE id IN (...)" query and returns how many rows changed.
    # It does NOT call save(): auto_now fields are not updated, so we set updated_at ourselves.
    if status == Task.Status.DONE:
        workspace_ids = list(
            tasks.values_list("project__workspace_id", flat=True).order_by().distinct()
        )
        # Invalidate their caches after the commit.
        for workspace_id in workspace_ids:
            _invalidate_workspace_cache(workspace_id)

        # Only tasks that aren't done yet get a new completion time.
        updated = tasks.exclude(status=Task.Status.DONE).update(
            status=status, completed_at=now, updated_at=now
        )
    else:
        # todo / in_progress: an open task never has a completion time.
        updated = tasks.update(status=status, completed_at=None, updated_at=now)

    # One INSERT for all the log rows.
    AuditLog.objects.bulk_create(
        [
            AuditLog(
                workspace_id=row["project__workspace_id"],
                actor=user,
                action="task.updated",
                target_type="task",
                target_id=row["id"],
                target_label=row["title"][:255],
                changes={"status": [row["status"], status]},
            )
            for row in old_rows
        ]
    )

    return updated


# Delete a task. (Before Phase 6 the ViewSet called task.delete() directly.)
def task_delete(*, task: Task, actor=None) -> None:
    # Remember the workspace before the row is gone.
    workspace_id = task.project.workspace_id
    with transaction.atomic():
        task.deleted_at = timezone.now()
        task.save(update_fields=["deleted_at", "updated_at"])

        # Audit log FIRST: after delete(), Django sets task.pk to None.
        audit_record(workspace_id=workspace_id, actor=actor, action="task.deleted", target=task)

    # The dashboard numbers changed.
    _invalidate_workspace_cache(workspace_id)


# Delete a project and, through CASCADE, all of its tasks.
def project_delete(*, project: Project) -> None:
    # Remember the workspace before the row is gone.
    workspace_id = project.workspace_id
    # DELETE the project, its tasks, and their comments.
    project.delete()
    # Many tasks disappeared: the dashboard numbers changed.
    _invalidate_workspace_cache(workspace_id)


# Bring a soft-deleted task back (Phase 10). Like Laravel's $task->restore().
def task_restore(*, task: Task, actor=None) -> Task:
    # Rule: only deleted tasks can be restored.
    if task.deleted_at is None:
        raise ValidationError({"task": "This task is not deleted."})
    # The change and its log row in one transaction.
    with transaction.atomic():
        task.deleted_at = None
        task.save(update_fields=["deleted_at", "updated_at"])
        audit_record(
            workspace_id=task.project.workspace_id,
            actor=actor,
            action="task.restored",
            target=task,
        )
    # The task counts again in the dashboard.
    _invalidate_workspace_cache(task.project.workspace_id)
    # Return the restored task.
    return task


def _apply_updates(*, instance, data: dict, allowed_fields: list[str]) -> list[str]:
    changed = []

    for field in allowed_fields:
        if field in data:
            setattr(instance, field, data[field])
            changed.append(field)
    return changed


def _validate_assignee(*, project: Project, assignee) -> None:
    if assignee is None:
        return

    is_member = Membership.objects.filter(workspace_id=project.workspace_id, user=assignee).exists()

    if not is_member:
        raise ValidationError({"assignee": "This assignee must be a member of this workspace"})


# Mark a workspace's cached data (dashboard...) as outdated, once the transaction commits.
def _invalidate_workspace_cache(workspace_id: int) -> None:
    # After the commit, NOT before: otherwise another request could rebuild the cache from
    # the old, not-yet-committed data, and store that under the new version.
    transaction.on_commit(lambda: bump_workspace_cache_version(workspace_id))


# Queue the "you were assigned" email, but only once the current transaction commits.
def _notify_assignee_after_commit(task: Task) -> None:
    # Copy the id into a local variable now. The lambda runs later, after the commit.
    task_id = task.id
    # transaction.on_commit(f): run f AFTER the transaction commits (never if it rolls back).
    # Outside a transaction (normal autocommit), it runs immediately.
    transaction.on_commit(lambda: notify_task_assigned.delay(task_id))


# Start a CSV export of a workspace's tasks. Returns at once; the file is built in the background.
def task_export_create(*, workspace, user) -> TaskExport:
    # Rule: one unfinished export per user and workspace at a time (no accidental duplicates).
    unfinished = [TaskExport.Status.PENDING, TaskExport.Status.RUNNING]
    if TaskExport.objects.filter(
        workspace=workspace, requested_by=user, status__in=unfinished
    ).exists():
        raise ValidationError({"workspace": "An export for this workspace is already running."})
    # Create the export row in "pending" state.
    export = TaskExport.objects.create(workspace=workspace, requested_by=user)
    # Queue the job only after the row is really committed (the worker must be able to read it).
    export_id = export.id

    transaction.on_commit(lambda: run_task_export.delay(export_id))
    # Return the pending export to the API.
    return export
