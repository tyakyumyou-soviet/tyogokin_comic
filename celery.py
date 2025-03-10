import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tyogokin_comic.settings')

app = Celery('tyogokin_comic')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
