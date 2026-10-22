# pytest.
import pytest

# Services to build test data.
from apps.projects.services import create_project
from apps.workspaces.services import workspace_create


# A workspace owned by "user" (the fixture from the root conftest.py).
# Fixtures in this file are available to EVERY test file in apps/projects/.
@pytest.fixture
def workspace(user):
    return workspace_create(name="Acme", owner=user)


# A project in that workspace.
@pytest.fixture
def project(workspace, user):
    return create_project(workspace=workspace, name="Website", key="web", created_by=user)
