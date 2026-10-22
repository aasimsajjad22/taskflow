from datetime import timedelta

from django.db.models import Count, F, OuterRef, Q, QuerySet
from django.db.models.expressions import Exists, Subquery
from django.utils import timezone

from apps.workspaces.selectors import workspace_ids_for_user

from .models import Comment, Project, Task, TaskExport, completed_late_q, open_q, overdue_q


def task_list_for_user(*, user) -> QuerySet[Task]:
    return (
        Task.objects.filter(project__workspace_id__in=workspace_ids_for_user(user=user))
        .select_related("project", "assignee", "reporter")
        .annotate(comment_count=Count("comments"))
    ).order_by("-created_at")


# The trash (Phase 10): soft-deleted tasks in the user's workspaces, most recently deleted first.
def task_trash_for_user(*, user) -> QuerySet[Task]:
    # all_objects: the manager that ALSO sees deleted tasks. Then keep only the deleted ones.
    return (
        Task.all_objects.filter(
            deleted_at__isnull=False,
            project__workspace_id__in=workspace_ids_for_user(user=user),
        )
        .select_related("project", "assignee", "reporter")
        # The task serializer shows comment_count, so the trash list needs it too.
        .annotate(comment_count=Count("comments"))
        .order_by("-deleted_at")
    )


def comment_list_for_task(*, task) -> QuerySet[Comment]:
    return task.comments.select_related("author")


def workspace_dashboard(*, workspace_id: int) -> dict:
    today = timezone.localdate()
    week_ago = timezone.now() - timedelta(days=7)

    tasks = Task.objects.filter(project__workspace__id=workspace_id)

    totals = tasks.aggregate(
        total=Count("id"),
        todo=Count("id", filter=Q(status=Task.Status.TODO)),
        in_progress=Count("id", filter=Q(status=Task.Status.IN_PROGRESS)),
        done=Count("id", filter=Q(status=Task.Status.DONE)),
        overdue=Count("id", filter=overdue_q()),
        due_next_7_days=Count(
            "id", filter=open_q() & Q(due_date__range=(today, today + timedelta(days=7)))
        ),
        completed_last_7_days=Count("id", filter=Q(completed_at__gte=week_ago)),
        completed_late=Count("id", filter=completed_late_q()),
    )

    per_assignee = (
        tasks.open()
        .filter(assignee__isnull=False)
        .values("assignee_id", email=F("assignee__email"))
        .annotate(open_tasks=Count("id"), overdue=Count("id", filter=overdue_q()))
        .order_by("-open_tasks", "email")
    )

    return {"totals": totals, "per_assignee": list(per_assignee)}


def project_list_for_user(*, user) -> QuerySet[Project]:

    latest_tasks = Task.objects.filter(project=OuterRef("pk")).order_by("-created_at")

    overdue_tasks = Task.objects.filter(project=OuterRef("pk")).overdue()

    return (
        Project.objects.filter(workspace_id__in=workspace_ids_for_user(user=user))
        .select_related("workspace", "created_by")
        .annotate(
            task_count=Count("tasks"),
            open_task_count=Count(
                "tasks", filter=Q(tasks__status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS])
            ),
            latest_task_title=Subquery(latest_tasks.values("title")[:1]),
            has_overdue_tasks=Exists(overdue_tasks),
        )
        .order_by("name")
    )


def task_export_list_for_user(*, user) -> QuerySet[Task]:
    return TaskExport.objects.filter(requested_by=user)
