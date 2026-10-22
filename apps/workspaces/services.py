from django.core.exceptions import ValidationError
from django.utils.text import slugify

from apps.audit.services import audit_record
from apps.workspaces.models import Membership, Workspace


def _unique_workspace_slug(name: str) -> str:
    base = slugify(name) or "workspace"

    slug = base
    counter = 2
    while Workspace.objects.filter(slug=slug).exists():
        slug = f"{base}_{counter}"
        counter += 1
    return slug


def workspace_create(*, name: str, owner) -> Workspace:
    workspace = Workspace.objects.create(name=name, slug=_unique_workspace_slug(name), owner=owner)

    Membership.objects.create(workspace=workspace, user=owner, role=Membership.Role.OWNER)
    return workspace


def workspace_update(*, workspace: Workspace, data: dict) -> Workspace:
    allowed_fields = ["name"]

    changed = []
    for field in allowed_fields:
        if field in data:
            setattr(workspace, field, data[field])
            changed.append(field)
    if changed:
        workspace.save(update_fields=[*changed, "updated_at"])

    return workspace


def membership_add(
    *, workspace: Workspace, user, role: str = Membership.Role.MEMBER, actor=None
) -> Membership:
    if Membership.objects.filter(workspace=workspace, user=user).exists():
        raise ValidationError({"email": "This user is already a member of this workspace"})

    membership = Membership.objects.create(workspace=workspace, user=user, role=role)

    audit_record(
        workspace_id=workspace.id,
        actor=actor,
        action="member.added",
        target=membership,
        changes={"user": [None, user.email], "role": [None, role]},
    )
    # Return the new membership.
    return membership
