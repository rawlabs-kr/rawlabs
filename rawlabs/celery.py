from __future__ import absolute_import

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rawlabs.settings')

app = Celery('rawlabs')

app.config_from_object(os.environ['DJANGO_SETTINGS_MODULE'], namespace='CELERY')

app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

# celery -A rawlabs worker --loglevel=info --concurrency=20 -d