# Security tests (Phase 10): one test per finding of our OWASP API Top 10 review,
# so a later change can't quietly bring a problem back.

# pytest.
import pytest

# respx: fake the outside services for the insights endpoint (Phase 8).
import respx

# Build URLs from route names.
from django.urls import reverse

# SimpleRateThrottle: the base class of all DRF throttles. Its THROTTLE_RATES dict is read
# ONCE, when DRF is imported, so the "settings" fixture can't change it. We change the
# dict itself with monkeypatch, which puts the old value back after the test.
from rest_framework.throttling import SimpleRateThrottle

# Factories and models.
from apps.projects.factories import ProjectFactory, TaskFactory
from apps.projects.models import TaskExport
from apps.workspaces.factories import MembershipFactory, WorkspaceFactory

pytestmark = pytest.mark.django_db


# A helper fixture: set ONE rate limit for the current test only, e.g. limit("exports", "2/hour").
@pytest.fixture
def limit(monkeypatch):
    def set_limit(scope, rate):
        # setitem changes one key of the dict, and monkeypatch restores it after the test.
        monkeypatch.setitem(SimpleRateThrottle.THROTTLE_RATES, scope, rate)

    return set_limit


# The baseline: every endpoint is limited per user.
def test_baseline_user_limit(client_for, limit):
    limit("user", "2/minute")
    client = client_for(WorkspaceFactory().owner)
    url = reverse("api:workspace-list")
    statuses = [client.get(url).status_code for _ in range(3)]
    assert statuses == [200, 200, 429]


# Exports: starting one is limited. The 429 uses our normal error format (Phase 2).
def test_starting_exports_is_limited(client_for, limit):
    limit("exports", "2/hour")
    workspace = WorkspaceFactory()
    client = client_for(workspace.owner)
    url = reverse("api:task-export-list")
    responses = [client.post(url, {"workspace": workspace.id}, format="json") for _ in range(3)]
    # 1st: accepted. 2nd: refused by the Phase 5 rule (one running export per workspace).
    # 3rd: refused by the rate limit, BEFORE any of our code runs.
    assert [r.status_code for r in responses] == [202, 400, 429]
    assert responses[2].json()["error"]["code"] == "throttled"


# Insights: each call costs 3 outside requests, so it's limited per user.
def test_insights_are_limited(client_for, limit, settings):
    limit("insights", "1/minute")
    settings.EXTERNAL_SERVICES_URL = "https://external.test"
    workspace = WorkspaceFactory()
    client = client_for(workspace.owner)
    url = reverse("api:workspace-insights", args=[workspace.id])
    # Fake the 3 outside services (Phase 8), so the first call works without the network.
    with respx.mock(base_url="https://external.test") as router:
        for path in ("/weather/", "/holidays/", "/exchange-rates/"):
            router.get(path).respond(json={})
        first = client.get(url)
        second = client.get(url)
    assert (first.status_code, second.status_code) == (200, 429)
    # The second call never reached the outside services: still 1 call per service.
    assert all(route.call_count == 1 for route in router.routes)


# Adding members says whether an email exists, so POST is limited. Listing is not affected.
def test_adding_members_is_limited(client_for, limit):
    limit("invites", "2/hour")
    workspace = WorkspaceFactory()
    client = client_for(workspace.owner)
    url = reverse("api:workspace-members", args=[workspace.id])
    statuses = [
        client.post(url, {"email": f"probe{i}@example.com"}, format="json").status_code
        for i in range(3)
    ]
    # 400 = "No user found with this email" (an answer an attacker learns from), then 429.
    assert statuses == [400, 400, 429]
    # GET (listing members) uses the baseline limit, not the invites limit.
    assert client.get(url).status_code == 200


# API1 (broken object level authorization): another member's export is invisible (404).
def test_cannot_read_someone_elses_export(client_for):
    workspace = WorkspaceFactory()
    export = TaskExport.objects.create(workspace=workspace, requested_by=workspace.owner)
    member = MembershipFactory(workspace=workspace).user
    response = client_for(member).get(reverse("api:task-export-detail", args=[export.id]))
    assert response.status_code == 404


# API3 (mass assignment): read-only fields in a PATCH are ignored, not saved.
def test_patch_cannot_change_protected_fields(client_for):
    task = TaskFactory()
    member = MembershipFactory(workspace=task.project.workspace).user
    # A project in another workspace where the same user is ALSO a member.
    other_project = ProjectFactory()
    MembershipFactory(workspace=other_project.workspace, user=member)
    response = client_for(member).patch(
        reverse("api:task-detail", args=[task.id]),
        {
            "title": "Allowed change",
            "project": other_project.id,
            "reporter": member.id,
            "completed_at": "2000-01-01T00:00:00Z",
        },
        format="json",
    )
    task.refresh_from_db()
    assert response.status_code == 200
    assert task.title == "Allowed change"
    # The protected fields did not change.
    assert task.project_id != other_project.id
    assert task.reporter_id != member.id
    assert task.completed_at is None


# API5 (broken function level authorization): nobody can make someone a second "owner".
def test_cannot_add_member_as_owner(client_for):
    workspace = WorkspaceFactory()
    new_user = MembershipFactory().user
    response = client_for(workspace.owner).post(
        reverse("api:workspace-members", args=[workspace.id]),
        {"email": new_user.email, "role": "owner"},
        format="json",
    )
    assert response.status_code == 400
    assert "role" in response.json()["error"]["details"]
