from celery import Celery
from celery.schedules import crontab
from geoapi.settings import settings

CELERY_CONNECTION_STRING = "amqp://{user}:{pwd}@{hostname}/{vhost}".format(
    user=settings.RABBITMQ_USERNAME,
    pwd=settings.RABBITMQ_PASSWD,
    hostname=settings.RABBITMQ_HOSTNAME,
    vhost=settings.RABBITMQ_VHOST
)

def make_celery(app):
    celery = Celery(
                app.import_name,
                backend='rpc',
                broker=CELERY_CONNECTION_STRING,
                include=['geoapi.tasks'])

    celery.conf.beat_schedule = {
    'refresh_observable_projects': {
        'task': 'geoapi.tasks.external_data.refresh_observable_projects',
        'schedule': crontab(hour='*', minute='0')
    }}

    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
