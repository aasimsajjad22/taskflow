from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.core.http import etag_matches, make_etag
from apps.projects.filters import TaskFilter
from apps.projects.models import Project, Task, TaskExport
from apps.projects.permissions import ProjectPermission, TaskPermission
from apps.projects.policies import can_manage_projects
from apps.projects.selectors import (
    comment_list_for_task,
    project_list_for_user,
    task_export_list_for_user,
    task_list_for_user,
    task_trash_for_user,
)
from apps.projects.serializers import (
    CommentSerializer,
    ProjectSerializer,
    TaskBulkStatusResultSerializer,
    TaskBulkStatusSerializer,
    TaskExportSerializer,
    TaskSerializer,
    TaskSerializerV2,
)
from apps.projects.services import (
    comment_create,
    create_project,
    project_delete,
    project_update,
    task_bulk_update_status,
    task_claim,
    task_create,
    task_delete,
    task_export_create,
    task_restore,
    task_update,
)


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer

    permission_classes = [IsAuthenticated, ProjectPermission]

    filterset_fields = ["workspace", "is_archived"]

    search_fields = ["name", "key"]

    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Project.objects.none()

        return project_list_for_user(user=self.request.user)

    def perform_create(self, serializer):

        data = serializer.validated_data

        if not can_manage_projects(user=self.request.user, workspace_id=data["workspace"]):
            raise PermissionDenied("Only workspace owners and admins can create projects.")

        project = create_project(
            workspace=data["workspace"],
            name=data["name"],
            key=data["key"],
            created_by=self.request.user,
            description=data.get("description", ""),
        )

        serializer.instance = self.get_queryset().get(pk=project.pk)

    def perform_update(self, serializer):

        serializer.instance = project_update(
            project=serializer.instance,
            data=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        project_delete(project=instance)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer

    def get_serializer_class(self):
        if self.request.version == "2":
            return TaskSerializerV2
        return super().get_serializer_class()

    permission_classes = [IsAuthenticated, TaskPermission]

    filterset_class = TaskFilter

    search_fields = ["title", "description"]

    ordering_fields = ["created_at", "due_date", "priority"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Task.objects.none()

        # The trash and restore actions work on DELETED tasks (Phase 10).
        if self.action in ("trash", "restore"):
            return task_trash_for_user(user=self.request.user)

        return task_list_for_user(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        task = self.get_object()
        # The ETag must change whenever the response would change. updated_at covers the
        # task's own fields; comment_count is in the response too, but adding a comment
        # does NOT change task.updated_at, so it must be part of the ETag as well.
        etag = make_etag("task", task.pk, task.updated_at.isoformat(), task.comment_count)

        if etag_matches(request, etag):
            response = Response(status=status.HTTP_304_NOT_MODIFIED)
        else:
            # Normal 200 with the full JSON.
            response = Response(self.get_serializer(task).data)

        response["ETag"] = etag

        response["Cache-Control"] = "private, no-cache"
        return response

    def perform_create(self, serializer):
        data = serializer.validated_data

        task = task_create(
            project=data["project"],
            title=data["title"],
            reporter=self.request.user,
            description=data.get("description", ""),
            priority=data.get("priority", Task.Priority.MEDIUM),
            assignee=data.get("assignee"),
            due_date=data.get("due_date"),
        )

        serializer.instance = self.get_queryset().get(pk=task.pk)

    def perform_update(self, serializer):
        serializer.instance = task_update(
            task=serializer.instance,
            data=serializer.validated_data,
            actor=self.request.user,
        )

    # Called by destroy() after get_object() (and TaskPermission's delete rule) succeeded.
    def perform_destroy(self, instance):
        # Delete through the service, so the cache is invalidated.
        task_delete(task=instance, actor=self.request.user)

    # GET /tasks/trash/ : soft-deleted tasks of my workspaces (Phase 10).
    # detail=False: a list, no id in the URL. Pagination and filters work as usual.
    @action(detail=False, methods=["get"])
    def trash(self, request):
        # list() uses get_queryset(), which returns the trash for this action.
        return self.list(request)

    # POST /tasks/{id}/restore/ : bring a deleted task back (Phase 10).
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        # Finds the task in the TRASH (get_queryset), and runs TaskPermission: only the
        # reporter or an owner/admin may restore, the same rule as deleting.
        task = task_restore(task=self.get_object(), actor=request.user)
        # Return it with the normal task shape (reload with comment_count).
        return Response(
            self.get_serializer(task_list_for_user(user=request.user).get(pk=task.pk)).data
        )

    @extend_schema(methods=["GET"], responses=CommentSerializer(many=True))
    @extend_schema(methods=["POST"], request=CommentSerializer, responses=CommentSerializer)
    @action(detail=True, methods=["POST", "GET"])
    def comments(self, request, pk=None):
        task = self.get_object()

        if request.method == "POST":
            serializer = CommentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            comment = comment_create(
                task=task,
                author=request.user,
                body=serializer.validated_data["body"],
            )

            return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)

        comments = comment_list_for_task(task=task)
        page = self.paginate_queryset(comments)

        return self.get_paginated_response(CommentSerializer(page, many=True).data)

    @extend_schema(request=None, responses=TaskSerializer)
    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None):
        task = self.get_object(self)

        task_claim(task_id=task.pk, user=request.user)
        task = self.get_queryset().get(pk=task.pk)

        return Response(self.get_serializer(task).data)

    @extend_schema(request=TaskBulkStatusSerializer, responses=TaskBulkStatusResultSerializer)
    @action(detail=False, methods=["post"], url_path="bulk-status")
    def bulk_status(self, request):
        serializer = TaskBulkStatusSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        updated = task_bulk_update_status(
            user=request.user,
            task_ids=serializer.validated_data["task_ids"],
            status=serializer.validated_data["status"],
        )
        # OUTPUT mode.
        return Response(TaskBulkStatusResultSerializer({"updated": updated}).data)


# /exports/ : start an export (POST), list my exports (GET), check one export (GET /exports/{id}/).
# Instead of ModelViewSet, we combine only the mixins we need: no update, no delete.
class TaskExportViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    # Input and output serializer.
    serializer_class = TaskExportSerializer

    # Phase 10: starting an export is expensive (a full workspace scan + a stored file),
    # so creating one has its own limit. Reading the status (polling) uses the baseline.
    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "exports"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    # Only the user's own exports.
    def get_queryset(self):
        # Empty queryset while the API docs are generated.
        if getattr(self, "swagger_fake_view", False):
            return TaskExport.objects.none()
        # The scoped query.
        return task_export_list_for_user(user=self.request.user)

    # Called by create() after validation.
    def perform_create(self, serializer):
        # Create the pending export and queue the job.
        serializer.instance = task_export_create(
            workspace=serializer.validated_data["workspace"],
            user=self.request.user,
        )

    # Docs: this endpoint answers 202, not 201.
    @extend_schema(responses={202: TaskExportSerializer})
    # Override create() only to change the status code.
    def create(self, request, *args, **kwargs):
        # Run the normal CreateModelMixin.create() (validation, perform_create, response).
        response = super().create(request, *args, **kwargs)
        # 202 Accepted = "I accepted your request, the work happens later".
        response.status_code = status.HTTP_202_ACCEPTED
        # Send the response.
        return response
