# Create your views here.
import asyncio
import time

from django.db import DatabaseError, connection
from django.http import JsonResponse


def health_check(request):

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        database_ok = True
    except DatabaseError:
        database_ok = False

    status_code = 200 if database_ok else 503

    return JsonResponse(
        {"status": "ok" if database_ok else "error", "database": database_ok},
        status=status_code,
    )


async def fake_external_service(request, name):
    # Simulate an outage.
    if request.GET.get("fail") == "1":
        return JsonResponse({"error": f"{name} is down"}, status=503)

    delay = float(request.GET.get("delay", "1"))

    await asyncio.sleep(delay)
    return JsonResponse({"service": name, "delay": delay, "value": f"some {name} data"})


# The same fake service written as a normal SYNC view, to compare under ASGI (Part 7).
def fake_external_service_sync(request, name):
    # How long to "work".
    delay = float(request.GET.get("delay", "1"))
    # time.sleep(): BLOCKS the whole thread for that long.
    time.sleep(delay)
    # The same answer as the async version.
    return JsonResponse({"service": name, "delay": delay, "value": f"some {name} data"})
