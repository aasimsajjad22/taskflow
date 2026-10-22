# BasePermission, and SAFE_METHODS = ("GET", "HEAD", "OPTIONS"): methods that only read.
from rest_framework.permissions import SAFE_METHODS, BasePermission

# Our policy function.
from .policies import can_delete_tasks, can_manage_projects


# Object-level rules for ProjectViewSet.
class ProjectPermission(BasePermission):
    # The message in the 403 error.
    message = "Only workspace owners and admins can change projects."

    # Runs inside get_object().
    def has_object_permission(self, request, view, obj):
        # Reading is allowed for every member.
        if request.method in SAFE_METHODS:
            return True
        # Editing, archiving, deleting: owners and admins. obj is the Project.
        # obj.workspace_id is a column on the project row: no extra query.
        return can_manage_projects(user=request.user, workspace_id=obj.workspace_id)


# Object-level rules for TaskViewSet.
class TaskPermission(BasePermission):
    # The message in the 403 error.
    message = "Only the task's reporter or a workspace owner/admin can delete this task."

    # Runs inside get_object().
    def has_object_permission(self, request, view, obj):
        # Only DELETE has a special rule. obj is the Task.
        if view.action in ("destroy", "restore"):
            return can_delete_tasks(user=request.user, task=obj)
        # Reading, editing, commenting: every member.
        return True
