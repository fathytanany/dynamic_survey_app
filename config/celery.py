import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("survey_platform")

app.config_from_object("django.conf:settings", namespace="CELERY")

# Discover tasks inside Django apps (looks for tasks.py / tasks/ in each app).
# The top-level tasks/ package is registered via CELERY_IMPORTS in settings.
app.autodiscover_tasks()
