import os
from celery import Celery
from django.conf import settings

# Définit le module des settings Django par défaut pour le programme 'celery'.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Crée l'instance de l'application Celery.
# Le premier argument, 'core', est le nom du projet courant.
app = Celery('core')

# Charge la configuration de Celery depuis les settings de Django.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Détecte et charge automatiquement les tâches définies dans les fichiers tasks.py
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """
    Tâche de débogage simple pour vérifier que la communication
    entre Django, le Broker (Redis) et le Worker Celery fonctionne.
    """
    print(f'Request: {self.request!r}')