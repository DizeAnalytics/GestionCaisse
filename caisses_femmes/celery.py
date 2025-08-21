import os
from celery import Celery

# Définir le module de paramètres Django par défaut
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'caisses_femmes.settings')

# Créer l'instance Celery
app = Celery('caisses_femmes')

# Charger la configuration depuis les paramètres Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Charger automatiquement les tâches depuis tous les fichiers tasks.py
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
