from apps.workspaces.models import Membership
from apps.workspaces.selectors import membership_role

MANAGER_ROLES = (Membership.Role.OWNER, Membership.Role.ADMIN)


def can_manage_workspace(*, user, workspace_id: int) -> bool:
    return membership_role(user=user, workspace_id=workspace_id) in MANAGER_ROLES


def can_delete_workspace(*, user, workspace_id: int) -> bool:
    # Compare the role with "owner".
    return membership_role(user=user, workspace_id=workspace_id) == Membership.Role.OWNER
