# settings.AUTH_USER_MODEL: our custom User model, by its "app.Model" name.
from django.conf import settings

# Django's model tools.
from django.db import models


# One row = one recorded change: WHO did WHAT to WHICH object, WHEN, and WHAT changed.
# Not a TimeStampedModel on purpose: log rows are never edited, so no updated_at.
class AuditLog(models.Model):
    # The workspace the change belongs to (so owners/admins can read their workspace's log).
    # CASCADE: deleting a workspace also deletes its log.
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="audit_logs"
    )
    # Who did it. SET_NULL: the log stays even if the user account is deleted later.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    # What happened, as "object.verb": "task.created", "task.updated", "member.added"...
    action = models.CharField(max_length=50)
    # Which object: its type ("task") and id. Plain columns, NOT a foreign key: the log
    # must survive when the object itself is deleted.
    target_type = models.CharField(max_length=50)
    target_id = models.PositiveBigIntegerField()
    # A readable name of the object AT THAT TIME (e.g. the task title), for the log view.
    target_label = models.CharField(max_length=255, blank=True)
    # What changed: {"status": ["todo", "done"]} = field -> [old value, new value].
    changes = models.JSONField(default=dict, blank=True)
    # When. auto_now_add: set once, when the row is created.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Newest first. "-id" breaks ties between rows created in the same instant.
        ordering = ["-created_at", "-id"]
        # The log view reads "one workspace, newest first": one index for exactly that query.
        indexes = [models.Index(fields=["workspace", "-created_at"], name="audit_ws_created_idx")]

    # Shown in the admin and the shell, e.g. "task.updated task#42".
    def __str__(self):
        return f"{self.action} {self.target_type}#{self.target_id}"
