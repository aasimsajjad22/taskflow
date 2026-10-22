import time

from asgiref.sync import async_to_sync
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from ..audit.selectors import audit_log_for_workspace
from ..audit.serializers import AuditLogSerializer
from ..projects.cache import cached_workspace_dashboard
from ..projects.serializers import WorkspaceDashboardSerializer
from .insights import fetch_workspace_insights
from .models import Workspace
from .permissions import WorkspacePermission
from .policies import can_manage_workspace
from .selectors import membership_list, user_can_manage_workspace, workspace_list_for_user
from .serializers import MembershipCreateSerializer, MembershipSerializer, WorkspaceSerializer
from .services import membership_add, workspace_create, workspace_update


class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer

    permission_classes = [IsAuthenticated, WorkspacePermission]

    search_fields = ["name"]

    ordering_fields = ["name", "created_at"]

    # Phase 10: stricter rate limits for two actions. DRF calls get_throttles() before
    # running the action; whatever it returns replaces the default (baseline) throttles.
    def get_throttles(self):
        # Every insights call triggers 3 outside requests: limit it per user.
        if self.action == "insights":
            # ScopedRateThrottle reads the rate from DEFAULT_THROTTLE_RATES[throttle_scope].
            self.throttle_scope = "insights"
            return [ScopedRateThrottle()]
        # Adding members (POST only, listing them is fine): limits email enumeration.
        if self.action == "members" and self.request.method == "POST":
            self.throttle_scope = "invites"
            return [ScopedRateThrottle()]
        # Everything else: the baseline anon/user limits.
        return super().get_throttles()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Workspace.objects.all()

        return workspace_list_for_user(user=self.request.user)

    def perform_create(self, serializer):

        workspace = workspace_create(
            name=serializer.validated_data["name"], owner=self.request.user
        )

        serializer.instance = self.get_queryset().get(pk=workspace.pk)

    def perform_update(self, serializer):
        workspace = serializer.instance

        if not user_can_manage_workspace(user=self.request.user, workspace=workspace):
            raise PermissionDenied("Only workspace owners and admins can edit this workspace.")

        serializer.instance = workspace_update(workspace=workspace, data=serializer.validated_data)

    @extend_schema(methods=["GET"], responses=MembershipSerializer(many=True))
    @extend_schema(
        methods=["POST"], request=MembershipCreateSerializer, responses=MembershipSerializer
    )
    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        workspace = self.get_object()

        if request.method == "POST":
            input_serializer = MembershipCreateSerializer(data=request.data)

            input_serializer.is_valid(raise_exception=True)

            membership = membership_add(
                workspace=workspace,
                user=input_serializer.validated_data["user"],
                role=input_serializer.validated_data["role"],
                actor=request.user,
            )

            return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

        memberships = membership_list(workspace=workspace)

        return Response(MembershipSerializer(memberships, many=True).data)

    @extend_schema(responses=WorkspaceDashboardSerializer)
    @action(detail=True, methods=["get"])
    def dashboard(self, request, pk=None):
        workspace = self.get_object()

        # From the cache when possible; otherwise two queries (and stored for next time).
        data, from_cache = cached_workspace_dashboard(workspace_id=workspace.id)
        # OUTPUT mode with a dict.
        response = Response(WorkspaceDashboardSerializer(data).data)
        # A debugging header: HIT = served from the cache, MISS = calculated now.
        response["X-Cache"] = "HIT" if from_cache else "MISS"
        # Send the response.
        return response

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"])
    def insights(self, request, pk=None):
        workspace = self.get_object()

        started = time.perf_counter()

        result = async_to_sync(fetch_workspace_insights)()

        result["workspace_id"] = workspace.id
        result["took_ms"] = round((time.perf_counter() - started) * 1000)
        # Send the JSON.
        return Response(result)

    # Docs: a paginated list of log rows.
    @extend_schema(responses=AuditLogSerializer(many=True))
    # GET /workspaces/{id}/audit-log/  (url_path: the URL uses a dash, the method an underscore)
    @action(detail=True, methods=["get"], url_path="audit-log")
    def audit_log(self, request, pk=None):
        # Members only (404 for others), like every workspace URL.
        workspace = self.get_object()
        # The log shows what EVERYONE did, so only owners and admins may read it.
        if not can_manage_workspace(user=request.user, workspace_id=workspace.id):
            raise PermissionDenied("Only owners and admins can see the audit log.")
        # Newest first, optionally only one kind: ?action=task.updated
        logs = audit_log_for_workspace(
            workspace_id=workspace.id, action=request.query_params.get("action")
        )
        # The normal pagination (Phase 2): ?page=2, max 100 per page.
        page = self.paginate_queryset(logs)
        return self.get_paginated_response(AuditLogSerializer(page, many=True).data)
