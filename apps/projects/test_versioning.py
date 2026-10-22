# pytest.
import pytest

# Build URLs from route names.
from django.urls import reverse

# Factories.
from apps.projects.factories import TaskFactory

pytestmark = pytest.mark.django_db

# The Accept header that asks for version 2.
V2 = "application/json; version=2"


# Old clients (no version) keep the version 1 shape: nothing breaks for them.
def test_default_is_version_1(client_for):
    task = TaskFactory(priority=3)
    body = client_for(task.reporter).get(reverse("api:task-detail", args=[task.id])).json()
    assert (body["priority"], body["priority_label"]) == (3, "High")


# Version 2: the priority is a word, and priority_label is gone.
def test_version_2_shape(client_for):
    task = TaskFactory(priority=3)
    url = reverse("api:task-detail", args=[task.id])
    body = client_for(task.reporter).get(url, HTTP_ACCEPT=V2).json()
    assert body["priority"] == "high"
    assert "priority_label" not in body


# Version 2 input: words in, numbers refused. An unknown version is refused with 406.
def test_version_2_input_and_unknown_version(client_for):
    task = TaskFactory()
    client = client_for(task.reporter)
    url = reverse("api:task-detail", args=[task.id])
    ok = client.patch(url, {"priority": "low"}, format="json", HTTP_ACCEPT=V2)
    bad = client.patch(url, {"priority": 3}, format="json", HTTP_ACCEPT=V2)
    unknown = client.get(url, HTTP_ACCEPT="application/json; version=3")
    assert ok.json()["priority"] == "low"
    assert bad.status_code == 400
    assert unknown.status_code == 406
