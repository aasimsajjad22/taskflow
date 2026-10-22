# shared_task: turns a normal function into a Celery task (a background job).
import csv
import io
import uuid

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils import timezone

# The email function from emails.py.
from .emails import email_overdue_digest, email_task_assigned

# Our models.
from .models import Task, TaskExport


# Background job: send the "you were assigned" email.
@shared_task(
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def notify_task_assigned(task_id: int) -> str:
    # Load the task FRESH from the database (we get only its id, see Step 2.9).
    # .filter().first() gives None instead of an error if the task was deleted meanwhile.
    task = Task.objects.select_related("project", "assignee").filter(pk=task_id).first()
    # Nothing to do if the task is gone or nobody is assigned anymore.
    if task is None or task.assignee is None:
        return "skipped: task or assignee missing"
    # Send the email (this is the slow part, now running in the worker).
    email_task_assigned(task=task)
    # The return value is printed in the worker log.
    return f"sent to {task.assignee.email}"


# How many overdue tasks to list in one digest email.
DIGEST_MAX_TASKS = 20


# SCHEDULED job (Celery Beat runs it every morning). It doesn't send emails itself:
# it finds who needs a digest and queues ONE small job per user ("fan-out").
@shared_task
def send_overdue_digests() -> int:
    # The ids of everyone who has at least one overdue task.
    user_ids = (
        Task.objects.overdue()
        .filter(assignee__isnull=False)
        # Only the assignee_id column.
        .values_list("assignee_id", flat=True)
        # IMPORTANT: .order_by() with no arguments removes Meta.ordering (created_at).
        # Otherwise created_at is added to the SELECT, and DISTINCT returns one row per TASK.
        .order_by()
        # One row per user.
        .distinct()
    )
    # Queue one job per user. If one user's email fails, the others are not affected.
    count = 0
    for user_id in user_ids:
        send_overdue_digest_to_user.delay(user_id)
        count += 1
    # Shown in the worker log, e.g. "succeeded: 6".
    return count


@shared_task(autoretry_for=(OSError,), retry_backoff=True, retry_backoff_max=600, max_retries=5)
def send_overdue_digest_to_user(user_id: int) -> str:
    today = timezone.localdate()

    key = f"overdue-digest:{user_id}:{today.isoformat()}"

    if not cache.add(key, "sent", timeout=60 * 60 * 24):
        return "skipped: already sent today"

    try:
        user = get_user_model().objects.filter(pk=user_id).first()
        overdue = Task.objects.overdue().filter(assignee_id=user_id)

        tasks = list(overdue.select_related("project").order_by("due_date")[:DIGEST_MAX_TASKS])
        if user is None or not tasks:
            return "skipped: nothing to send"

        email_overdue_digest(user=user, tasks=tasks, total=overdue.count())

    except Exception:
        cache.delete(key)
        # Re-raise the error, so Celery sees the failure (and retries for OSError).
        raise

    return f"sent to {user.email}"


# The column names in the first line of the CSV.
CSV_HEADER = [
    "id",
    "project",
    "title",
    "status",
    "priority",
    "assignee",
    "due_date",
    "completed_at",
]


# Build the CSV file for one TaskExport. Can take a while for big workspaces.
@shared_task
def run_task_export(export_id: int) -> str:
    # Move the export from "pending" to "running" with ONE atomic UPDATE (Phase 4).
    # If two workers get the same job (e.g. after a crash with acks_late), only ONE
    # of them changes a row; the other gets 0 and stops. That makes the job idempotent.
    claimed = TaskExport.objects.filter(pk=export_id, status=TaskExport.Status.PENDING).update(
        status=TaskExport.Status.RUNNING, updated_at=timezone.now()
    )
    if claimed == 0:
        return "skipped: not pending"
    # Load the export (now "running").
    export = TaskExport.objects.get(pk=export_id)
    try:
        # An in-memory text buffer that behaves like an open file.
        buffer = io.StringIO()
        # A CSV writer that writes rows into the buffer.
        writer = csv.writer(buffer)
        # The header row.
        writer.writerow(CSV_HEADER)
        # All tasks of the workspace, with project and assignee in the same query.
        tasks = (
            Task.objects.filter(project__workspace_id=export.workspace_id)
            .select_related("project", "assignee")
            .order_by("id")
        )
        # Count the rows as we write them.
        row_count = 0
        # .iterator(chunk_size=2000): read rows from PostgreSQL 2000 at a time, without
        # keeping all 20,000 Task objects in memory at once.
        for task in tasks.iterator(chunk_size=2000):
            # One CSV line per task. "or ''" writes an empty cell instead of "None".
            writer.writerow(
                [
                    task.id,
                    task.project.key,
                    task.title,
                    task.status,
                    task.get_priority_display(),
                    task.assignee.email if task.assignee else "",
                    task.due_date or "",
                    task.completed_at or "",
                ]
            )
            row_count += 1
        # A random file name, so nobody can guess another workspace's file URL.
        filename = f"tasks-{export.workspace_id}-{uuid.uuid4().hex}.csv"
        # Save the file into MEDIA_ROOT/exports/ and store its path on the export.
        # save=False: don't save the model yet (we save everything once below).
        export.file.save(filename, ContentFile(buffer.getvalue().encode("utf-8")), save=False)
        # Mark it as done.
        export.status = TaskExport.Status.DONE
        export.row_count = row_count
        export.finished_at = timezone.now()
        export.save(update_fields=["file", "status", "row_count", "finished_at", "updated_at"])
    except Exception as error:
        # Something broke: record it, so the user sees "failed" and the reason.
        export.status = TaskExport.Status.FAILED
        export.error = str(error)[:1000]
        export.finished_at = timezone.now()
        export.save(update_fields=["status", "error", "finished_at", "updated_at"])
        # Re-raise, so the failure also shows in the worker log (and in Sentry later).
        raise
    # Shown in the worker log.
    return f"exported {row_count} rows"
