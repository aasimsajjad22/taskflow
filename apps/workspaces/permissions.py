from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from apps.workspaces.policies import can_delete_workspace, can_manage_workspace


class WorkspacePermission(BasePermission):
    message = "You do not have permission to perform this action on a workspace"

    def has_object_permission(self, request: Request, view, obj) -> bool:
        if view.action == "destroy":
            return can_delete_workspace(user=request.user, workspace_id=obj.id)

        if view.action in ("update", "partial_update"):
            return can_manage_workspace(user=request.user, workspace_id=obj.id)

        if view.action == "members" and request.method == "POST":
            return can_manage_workspace(user=request.user, workspace_id=obj.id)

        return True
