from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "error_dict") else exc.messages

        exc = exceptions.ValidationError(detail=detail)
    elif isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)

    if response is None:
        return None

    if isinstance(exc, exceptions.ValidationError):
        message = "Invalid input."
        details = response.data
    else:
        message = response.data.get("detail", "Something went wrong.")
        details = None

    response.data = {
        "error": {
            "status": response.status_code,
            "code": getattr(exc, "default_code", "error"),
            "message": str(message),
            "details": details,
        }
    }

    return response
