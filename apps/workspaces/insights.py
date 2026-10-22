# asyncio: run several waiting operations at the same time.
import asyncio
import logging

# httpx: HTTP client with an async mode (AsyncClient).
import httpx

# settings: base URL and timeout of the external services.
from django.conf import settings

# The external sources: our name for each -> its path (with a fake delay in development).
INSIGHT_SOURCES = {
    "weather": "/weather/?delay=1",
    "holidays": "/holidays/?delay=1",
    "holidayx": "/holidays/?fail=1",
    "exchange_rates": "/exchange-rates/?delay=5",
}

logger = logging.getLogger(__name__)


# Call ONE source. Never raises: returns (name, data, error) so one failure can't break the rest.
async def _fetch_source(client: httpx.AsyncClient, name: str, path: str):
    try:
        # "await": start the request and give control back to the event loop while we wait.
        response = await client.get(path)
        # Turn 4xx/5xx answers into an exception (like Laravel's ->throw()).
        response.raise_for_status()
        # Success: the parsed JSON, and no error.
        return name, response.json(), None
    # httpx.HTTPError covers timeouts, refused connections, and bad status codes.
    # The service didn't answer in time (connect or read took too long).
    except httpx.TimeoutException:
        # Log it for us, with the source name.
        logger.warning("External source %s timed out", name)
        # A short, safe code for the API user.
        return name, None, "timeout"
    # Everything else: refused connection, DNS error, 4xx/5xx status codes...
    except httpx.HTTPError as error:
        # The full details (including internal URLs) go ONLY to our logs.
        logger.warning("External source %s failed: %s", name, error)
        # A short, safe code for the API user. Never send internal URLs or stack traces.
        return name, None, "unavailable"


# Call ALL sources at the same time and collect the results.
async def fetch_workspace_insights() -> dict:
    # One timeout for each request (connect + read), from settings.
    timeout = httpx.Timeout(settings.EXTERNAL_TIMEOUT_SECONDS)
    # Where the services live, from settings.
    base_url = settings.EXTERNAL_SERVICES_URL
    # One AsyncClient for all calls (reuses connections). "async with" closes it at the end.
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        # Build one "waiting call" per source, then run them ALL together with gather().
        # gather() returns when the last one finishes, so the total time = the slowest call.
        results = await asyncio.gather(
            *(_fetch_source(client, name, path) for name, path in INSIGHT_SOURCES.items())
        )
    # Split the results into successful data and errors.
    data = {name: payload for name, payload, error in results if error is None}
    errors = {name: error for name, payload, error in results if error is not None}
    # The final dict for the API.
    return {"data": data, "errors": errors}
