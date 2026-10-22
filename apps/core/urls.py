from django.conf import settings
from django.urls import path

from .views import fake_external_service, fake_external_service_sync, health_check

app_name = "core"

urlpatterns = [
    path("health/", health_check, name="health_check"),
]

# Fake slow external services, for the async lessons. Only when DEBUG is on (never in production).
if settings.DEBUG:
    urlpatterns += [
        # /fake/weather/?delay=1 -> async fake service.
        path("fake/<slug:name>/", fake_external_service, name="fake-service"),
        # /fake-sync/weather/?delay=1 -> sync fake service (for the ASGI comparison).
        path("fake-sync/<slug:name>/", fake_external_service_sync, name="fake-service-sync"),
    ]
