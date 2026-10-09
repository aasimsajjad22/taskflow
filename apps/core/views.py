# Create your views here.

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
