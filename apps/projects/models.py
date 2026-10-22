from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.workspaces.models import Workspace


class Project(TimeStampedModel):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="projects",
    )

    name = models.CharField(max_length=255)

    key = models.CharField(max_length=32)

    description = models.TextField(blank=True)

    is_archived = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_projects",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "key"],
                name="unique_project_key_per_workspace",
            )
        ]

    def __str__(self):
        return f"{self.key} - {self.name}"


def open_q() -> Q:
    return ~Q(status=Task.Status.DONE)


def overdue_q() -> Q:
    return open_q() & Q(due_date__lt=timezone.localdate())


def completed_late_q() -> Q:
    return Q(status=Task.Status.DONE, completed_at__date__gt=F("due_date"))


class TaskQuerySet(models.QuerySet):
    # Tasks that are not done.
    def open(self):
        return self.filter(open_q())

    # Open tasks with a due date in the past.
    def overdue(self):
        return self.filter(overdue_q())

    # Done tasks that were finished after their due date.
    def completed_late(self):
        return self.filter(completed_late_q())

    # Tasks with nobody assigned.
    def unassigned(self):
        return self.filter(assignee__isnull=True)


# Phase 10: the DEFAULT manager hides soft-deleted tasks. Every existing query (selectors,
# dashboard, digest, export, claim, bulk...) gets "deleted_at IS NULL" automatically.
# from_queryset(TaskQuerySet): keeps our scopes, so Task.objects.overdue() still works.
class TaskManager(models.Manager.from_queryset(TaskQuerySet)):
    # get_queryset() is the starting point of every Task.objects... query.
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Task(TimeStampedModel):
    class Status(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="tasks",
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TODO, db_index=True
    )

    priority = models.PositiveSmallIntegerField(
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reported_tasks",
    )

    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    deleted_at = models.DateTimeField(null=True, blank=True)

    # Use our custom QuerySet. Now Task.objects.overdue() works, and so does
    # Task.objects.filter(...).overdue(), because every QuerySet method returns a TaskQuerySet.
    # objects = TaskQuerySet.as_manager()

    # The default manager: only tasks that are NOT deleted (see TaskManager above).
    # The FIRST manager in the class is Django's default one, so keep this order.
    objects = TaskManager()
    # ALL tasks, deleted ones included: for the trash, restoring, and cleanup jobs.
    # Like Laravel's Task::withTrashed().
    all_objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"], name="task_project_status_idx"),
            models.Index(
                fields=["due_date"], name="task_due_date_idx", condition=~Q(status="done")
            ),
        ]

    def __str__(self):
        return f"{self.title}"


class Comment(TimeStampedModel):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="comments",
    )

    body = models.TextField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.body[:50]


# One CSV export request. The file is built in the background by a Celery job.
class TaskExport(TimeStampedModel):
    # The life of an export: pending -> running -> done (or failed).
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    # Which workspace's tasks to export.
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="task_exports")
    # Who asked for it. Only this user can see the export.
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_exports"
    )
    # Current state. Starts as "pending".
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    # The finished CSV file. FileField stores the PATH in the database; the file itself goes
    # into MEDIA_ROOT/exports/. blank=True: empty until the job is done.
    file = models.FileField(upload_to="exports/", blank=True)
    # How many tasks are in the file.
    row_count = models.PositiveIntegerField(default=0)
    # The error message if the job failed.
    error = models.TextField(blank=True)
    # When the job finished (done or failed).
    finished_at = models.DateTimeField(null=True, blank=True)

    # Model settings.
    class Meta:
        # Newest exports first.
        ordering = ["-created_at"]

    # e.g. "Export 5 (done)"
    def __str__(self):
        return f"Export {self.id} ({self.status})"
