# Role names and the role selector come from the workspaces app.
from apps.workspaces.models import Membership
from apps.workspaces.selectors import membership_role

# Roles that can manage projects.
MANAGER_ROLES = (Membership.Role.OWNER, Membership.Role.ADMIN)


# Can the user create, edit, archive, or delete projects in this workspace?
def can_manage_projects(*, user, workspace_id: int) -> bool:
    # Owners and admins only.
    return membership_role(user=user, workspace_id=workspace_id) in MANAGER_ROLES


def can_delete_tasks(*, user, task) -> bool:
    if task.reporter_id == user.id:
        return True

    return membership_role(user=user, workspace_id=task.project.workspace_id) in MANAGER_ROLES
