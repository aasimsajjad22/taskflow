# AppConfig holds the settings for one app.
from django.apps import AppConfig


# Configuration class for the "audit" app (Phase 10).
class AuditConfig(AppConfig):
    # Default type of auto "id" primary keys for models in this app (big integer).
    default_auto_field = "django.db.models.BigAutoField"
    # Full Python path to the app. Must match the folder: apps/audit -> "apps.audit".
    name = "apps.audit"
