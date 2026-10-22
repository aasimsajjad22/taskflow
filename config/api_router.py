from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.projects.views import ProjectViewSet, TaskExportViewSet, TaskViewSet
from apps.workspaces.views import WorkspaceViewSet

router = DefaultRouter()

router.register("workspaces", WorkspaceViewSet, basename="workspace")
router.register("projects", ProjectViewSet, basename="project")
router.register("tasks", TaskViewSet, basename="task")

router.register("exports", TaskExportViewSet, basename="task-export")

app_name = "api"

urlpatterns = [*router.urls, path("auth/", include("apps.users.urls"))]
