from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Workspace(TimeStampedModel):
    name = models.CharField(max_length=255)

    slug = models.SlugField(max_length=255, unique=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_workspaces"
    )

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="Membership", related_name="workspaces"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        ADMIN = "admin"
        OWNER = "owner"
        MEMBER = "member"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        ordering = ["created_at"]

        constraints = [
            models.UniqueConstraint(fields=["workspace", "user"], name="unique_workspace_member")
        ]

    def __str__(self):
        return f"{self.user} in {self.workspace} ({self.role})"
