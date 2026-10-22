# Django's cache (in-memory "locmem" in tests, see config/settings/test.py).
import pytest
from django.core.cache import cache

# DRF's test client.
from rest_framework.test import APIClient

# Builds User rows for tests.
from apps.users.factories import UserFactory


# autouse=True: this fixture runs before EVERY test, without being asked for.
# The in-memory test cache lives as long as the pytest process, so without this, a value
# cached by one test (a dashboard, a "digest sent" marker...) would leak into the next test.
@pytest.fixture(autouse=True)
def clear_cache():
    # Empty the cache before the test.
    cache.clear()
    # "yield" = run the test here. (Code after it would run after the test.)
    yield


# A saved user. Used by the workspace/project fixtures in apps/projects/conftest.py.
# "db" = this fixture needs database access.
@pytest.fixture
def user(db):
    return UserFactory()


# A FACTORY fixture: it returns a function, so one test can make clients for several users.
# Usage: client_for(some_user).get(url)
@pytest.fixture
def client_for():
    def _make(user):
        client = APIClient()
        # Skip real login (JWT): every request from this client is made as "user".
        client.force_authenticate(user=user)
        return client

    return _make
