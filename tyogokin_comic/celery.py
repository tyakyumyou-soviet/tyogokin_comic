import os
from celery import Celery

# Djangoの設定モジュールを設定する
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tyogokin_comic.settings')

app = Celery('tyogokin_comic')

# Djangoの設定をCeleryに取り込む。設定はCELERY_というプレフィックスが必要。
app.config_from_object('django.conf:settings', namespace='CELERY')

# Djangoアプリケーションのタスクモジュールを自動発見する
app.autodiscover_tasks()
