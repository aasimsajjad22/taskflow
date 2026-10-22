# DRF serializers.
from rest_framework import serializers

# The small user shape we use everywhere ({id, email, full_name}).
from apps.users.serializers import UserSummarySerializer

# The model.
from .models import AuditLog


# OUTPUT only: one log row.
class AuditLogSerializer(serializers.ModelSerializer):
    # Who did it, or null (system action, or the user was deleted later).
    actor = UserSummarySerializer(read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "action",
            "actor",
            "target_type",
            "target_id",
            "target_label",
            "changes",
            "created_at",
        ]
        # Logs are never written through the API.
        read_only_fields = fields
