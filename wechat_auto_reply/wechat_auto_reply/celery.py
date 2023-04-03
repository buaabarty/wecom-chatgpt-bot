# celery.py
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# 设置Django项目的默认配置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wechat_auto_reply.settings')

app = Celery('wechat_auto_reply')

# 从Django的设置中加载Celery配置
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现Celery任务
app.autodiscover_tasks()