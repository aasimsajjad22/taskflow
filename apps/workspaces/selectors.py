from django.db.models import Count, QuerySet

from .models import Membership, Workspace


def workspace_ids_for_user(*, user) -> QuerySet:
    return Membership.objects.filter(user=user).values("workspace_id")


def workspace_list_for_user(*, user) -> QuerySet:
    return (
        Workspace.objects.filter(id__in=workspace_ids_for_user(user=user))
        .select_related("owner")
        .annotate(member_count=Count("memberships"))
        .order_by("name")
    )


def user_is_member(*, user, workspace) -> bool:
    return Membership.objects.filter(user=user, workspace=workspace).exists()


def user_can_manage_workspace(*, user, workspace) -> bool:
    return Membership.objects.filter(
        user=user,
        workspace=workspace,
        role__in=[Membership.Role.OWNER, Membership.Role.ADMIN],
    ).exists()


def membership_list(*, workspace) -> QuerySet[Membership]:
    return workspace.memberships.select_related("user")


def membership_role(*, user, workspace_id: int) -> str | None:
    return (
        Membership.objects.filter(user=user, workspace_id=workspace_id)
        .values_list("role", flat=True)
        .first()
    )
