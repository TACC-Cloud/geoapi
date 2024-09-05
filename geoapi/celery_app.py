from celery import Celery
from celery.schedules import crontab
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
    'refresh_watch_content_projects': {
        'task': 'geoapi.tasks.external_data.refresh_watch_content_projects',
        'schedule': crontab(hour='*', minute='0')
    }
}
