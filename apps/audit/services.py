import datetime

from apps.audit.models import AuditLog
from apps.realtime.events import publish_workspace_event


def _json_value(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if hasattr(value, "pk"):
        return value.pk

    return value


def audit_diff(before: dict, after: dict) -> dict:
    return {
        field: [_json_value(before[field]), _json_value(after[field])]
        for field in before
        if before[field] != after[field]
    }


# Record one change. Call it INSIDE the same transaction as the change itself: if the change
# is rolled back, its log row is rolled back too, so the log never lies.
def audit_record(*, workspace_id: int, actor, action: str, target, changes=None) -> AuditLog:
    log = AuditLog.objects.create(
        workspace_id=workspace_id,
        # Background jobs or system code may have no user: store NULL then.
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        # "task", "membership"...: the model's lowercase name.
        target_type=target._meta.model_name,
        target_id=target.pk,
        # str(task) at this moment, cut to the column size.
        target_label=str(target)[:255],
        changes=changes or {},
    )

    # Every recorded change is also a live event (sent after the commit, see events.py).
    # One place for "something changed", instead of a publish call in every service.
    publish_workspace_event(
        workspace_id=workspace_id,
        event=action,
        data={"target_type": log.target_type, "target_id": log.target_id},
    )
    # Return the log row.
    return log

    return log
