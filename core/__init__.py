# S'assure que l'application Celery est importée lorsque Django démarre.
from .celery import app as celery_app

__all__ = ('celery_app',)