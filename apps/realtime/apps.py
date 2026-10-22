# AppConfig holds the settings for one app.
from django.apps import AppConfig


# Configuration class for the "realtime" app (Phase 10: WebSockets).
class RealtimeConfig(AppConfig):
    # Default type of auto "id" primary keys (this app has no models, but keep it consistent).
    default_auto_field = "django.db.models.BigAutoField"
    # Full Python path to the app.
    name = "apps.realtime"
