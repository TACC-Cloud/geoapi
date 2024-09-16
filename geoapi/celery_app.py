from celery import Celery
from datetime import timedelta
from geoapi.settings import settings


CELERY_CONNECTION_STRING = "amqp://{user}:{pwd}@{hostname}/{vhost}".format(
    user=settings.RABBITMQ_USERNAME,
    pwd=settings.RABBITMQ_PASSWD,
    hostname=settings.RABBITMQ_HOSTNAME,
    vhost=settings.RABBITMQ_VHOST
)

app = Celery('hello',
             backend='rpc',
             broker=CELERY_CONNECTION_STRING,
             include=['geoapi.tasks'])

app.conf.beat_schedule = {
    'refresh_projects_watch_content': {
        'task': 'geoapi.tasks.external_data.refresh_projects_watch_content',
        'schedule': timedelta(hours=1)
    },
    'refresh_projects_watch_users': {
        'task': 'geoapi.tasks.external_data.refresh_projects_watch_users',
        'schedule': timedelta(minutes=30)
    }
}
