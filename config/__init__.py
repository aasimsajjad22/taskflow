# Load the Celery app every time Django starts (runserver, shell, workers...).
# Then @shared_task functions know which Celery app to use.
from .celery import app as celery_app

# __all__ lists the names this package "exports". It also tells Ruff the import is used on purpose.
__all__ = ("celery_app",)
