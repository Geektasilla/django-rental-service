import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
# Namespaced so every Celery-related Django setting is prefixed CELERY_ (see config/settings.py).
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
