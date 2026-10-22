from apps.audit.models import AuditLog


def audit_log_for_workspace(*, workspace_id: int, action: str | None = None):
    logs = AuditLog.objects.filter(workspace_id=workspace_id).select_related("actor")

    if action:
        logs = logs.filter(action=action)
    return logs
