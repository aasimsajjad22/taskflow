from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.projects.models import Comment, Project, Task, TaskExport
from apps.users.models import User
from apps.users.serializers import UserSummarySerializer
from apps.workspaces.selectors import user_is_member


class ProjectSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True, allow_null=True)
    # The next four come from annotations in project_list_for_user (Part 5).
    # read_only: they are calculated, never sent by the client.
    task_count = serializers.IntegerField(read_only=True)
    open_task_count = serializers.IntegerField(read_only=True)
    # allow_null: a project with no tasks has no latest task (the subquery gives NULL).
    latest_task_title = serializers.CharField(read_only=True, allow_null=True)
    has_overdue_tasks = serializers.BooleanField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "workspace",
            "name",
            "key",
            "description",
            "is_archived",
            "created_by",
            "created_at",
            "updated_at",
            "task_count",
            "open_task_count",
            "latest_task_title",
            "has_overdue_tasks",
        ]

        read_only_fields = ["created_at", "updated_at"]

    def validate_workspace(self, workspace):
        user = self.context["request"].user
        if not user_is_member(user=user, workspace=workspace):
            raise serializers.ValidationError("You are not a member of this workspace.")
        return workspace

    def validate_key(self, value):
        return value.upper()


class TaskSerializer(serializers.ModelSerializer):
    assignee = UserSummarySerializer(read_only=True, allow_null=True)

    assignee_id = serializers.PrimaryKeyRelatedField(
        source="assignee",
        queryset=User.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    reporter = UserSummarySerializer(read_only=True, allow_null=True)

    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    comment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Task
        # Fields in the JSON.
        fields = [
            "id",
            "project",
            "title",
            "description",
            "status",
            "priority",
            "priority_label",
            "assignee",
            "assignee_id",
            "reporter",
            "due_date",
            "completed_at",
            "comment_count",
            "created_at",
            "updated_at",
        ]
        # completed_at is set by the service only.
        read_only_fields = ["completed_at", "created_at", "updated_at"]

    def validate_project(self, project):
        user = self.context["request"].user
        # Check membership of the project's workspace.
        if not user_is_member(user=user, workspace=project.workspace):
            raise serializers.ValidationError("You are not a member of this project's workspace.")

        return project


# Phase 10: the priority as a word ("low", "medium", "high") instead of a number.
# A custom field: to_representation() = output (number -> word),
# to_internal_value() = input (word -> number, or a 400 error).
# extend_schema_field: tells the API docs it's a string with three allowed values.
@extend_schema_field({"type": "string", "enum": ["low", "medium", "high"]})
class PriorityNameField(serializers.Field):
    # Number (as stored in the database) -> word.
    NAMES = {
        Task.Priority.LOW: "low",
        Task.Priority.MEDIUM: "medium",
        Task.Priority.HIGH: "high",
    }

    # OUTPUT: 3 -> "high".
    def to_representation(self, value):
        return self.NAMES[value]

    # INPUT: "high" -> 3. Anything else -> a field error.
    def to_internal_value(self, data):
        for number, name in self.NAMES.items():
            if data == name:
                return number
        raise serializers.ValidationError('Must be "low", "medium" or "high".')


class TaskSerializerV2(TaskSerializer):
    priority = PriorityNameField(required=False)

    class Meta(TaskSerializer.Meta):
        fields = [f for f in TaskSerializer.Meta.fields if f != "priority_label"]


class CommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True, allow_null=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "body", "created_at"]
        read_only_fields = ["created_at"]


# OUTPUT ONLY: the "totals" part of the dashboard.
# A plain Serializer can format a dict too, not only model objects.
class DashboardTotalsSerializer(serializers.Serializer):
    # Every key from the aggregate() dict, each a whole number.
    total = serializers.IntegerField()
    # Count per status.
    todo = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    done = serializers.IntegerField()
    # Open tasks past their due date.
    overdue = serializers.IntegerField()
    # Open tasks due in the next 7 days.
    due_next_7_days = serializers.IntegerField()
    # Tasks finished in the last 7 days.
    completed_last_7_days = serializers.IntegerField()
    # Tasks finished after their due date.
    completed_late = serializers.IntegerField()


# OUTPUT ONLY: one row of the "per assignee" list.
class AssigneeStatsSerializer(serializers.Serializer):
    # The user's id and email (from values("assignee_id", email=...)).
    assignee_id = serializers.IntegerField()
    email = serializers.EmailField()
    # Their open tasks, and how many of those are overdue.
    open_tasks = serializers.IntegerField()
    overdue = serializers.IntegerField()


# OUTPUT ONLY: the whole dashboard. Nested serializers describe the shape.
class WorkspaceDashboardSerializer(serializers.Serializer):
    # One nested object.
    totals = DashboardTotalsSerializer()
    # A nested list (many=True).
    per_assignee = AssigneeStatsSerializer(many=True)


# INPUT ONLY: the body of the bulk status endpoint.
class TaskBulkStatusSerializer(serializers.Serializer):
    # A list of task ids. child=... checks each item. 1 to 100 ids per request.
    task_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=1, max_length=100
    )
    # The new status: one of the Task.Status values.
    status = serializers.ChoiceField(choices=Task.Status.choices)


# OUTPUT ONLY: how many tasks were changed.
class TaskBulkStatusResultSerializer(serializers.Serializer):
    # The number of rows the UPDATE changed.
    updated = serializers.IntegerField()


# INPUT: the workspace to export. OUTPUT: the export's state and, when done, the file URL.
class TaskExportSerializer(serializers.ModelSerializer):
    # ModelSerializer settings.
    class Meta:
        # Built from the TaskExport model.
        model = TaskExport
        # Fields in the JSON. "file" becomes a full download URL (DRF builds it with the request).
        fields = [
            "id",
            "workspace",
            "status",
            "row_count",
            "error",
            "file",
            "created_at",
            "finished_at",
        ]
        # Only "workspace" can be sent. Everything else is set by the job.
        read_only_fields = ["status", "row_count", "error", "file", "created_at", "finished_at"]

    # The user must be a member of the workspace they want to export.
    def validate_workspace(self, workspace):
        # The logged-in user, from the context the view passes in.
        user = self.context["request"].user
        # Not a member? Reject.
        if not user_is_member(user=user, workspace=workspace):
            raise serializers.ValidationError("You are not a member of this workspace.")
        # Return the value.
        return workspace
