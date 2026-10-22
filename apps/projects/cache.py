# Django's cache (Redis, configured in Phase 5).
from django.core.cache import cache

# The expensive function we want to cache.
from .selectors import workspace_dashboard

# How long a cached dashboard may live, in seconds (5 minutes). A safety net:
# even if we forget to invalidate somewhere, the data is at most 5 minutes old.
DASHBOARD_TTL = 5 * 60


# The cache key that holds a workspace's current VERSION number.
def _version_key(workspace_id: int) -> str:
    return f"workspace:{workspace_id}:version"


# Read the workspace's current cache version (starts at 1).
def get_workspace_cache_version(workspace_id: int) -> int:
    # cache.get() returns None when the key doesn't exist yet.
    version = cache.get(_version_key(workspace_id))
    if version is None:
        # First time: store 1. timeout=None = never expires. add() won't overwrite if another
        # request stored it at the same moment.
        cache.add(_version_key(workspace_id), 1, timeout=None)
        # Read it again (it's 1, or a newer number if someone bumped it in between).
        version = cache.get(_version_key(workspace_id), 1)
    return version


# Make ALL cached data of a workspace outdated at once, by moving to a new version number.
def bump_workspace_cache_version(workspace_id: int) -> None:
    try:
        # incr() adds 1 inside Redis (atomic: two bumps at once give +2, never +1).
        cache.incr(_version_key(workspace_id))
    except ValueError:
        # The version key doesn't exist yet (incr() raises ValueError for a missing key).
        # Start at 2, so it differs from the default 1 that old keys may have used.
        cache.set(_version_key(workspace_id), 2, timeout=None)


# The key for the dashboard of a workspace, including its current version.
# e.g. "workspace:3:v7:dashboard". After a bump it becomes "...:v8:...": a different key.
def dashboard_cache_key(workspace_id: int) -> str:
    version = get_workspace_cache_version(workspace_id)
    return f"workspace:{workspace_id}:v{version}:dashboard"


# The dashboard, from the cache when possible. Returns (data, came_from_cache).
def cached_workspace_dashboard(workspace_id: int) -> tuple[dict, bool]:
    # The key for the CURRENT version.
    key = dashboard_cache_key(workspace_id)
    # Fast path: it's in the cache.
    data = cache.get(key)
    if data is not None:
        return data, True
    # Not cached: run the expensive queries and store the result for next time.
    data = workspace_dashboard(workspace_id=workspace_id)
    cache.set(key, data, timeout=DASHBOARD_TTL)
    return data, False
