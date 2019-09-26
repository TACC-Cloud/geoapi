from celery import Celery
from geoapi.settings import settings
import geoapi.tasks.external_data

CELERY_CONNECTION_STRING = "amqp://{user}:{pwd}@{hostname}/{vhost}".format(
    user=settings.RABBITMQ_USERNAME,
    pwd=settings.RABBITMQ_PASSWD,
    hostname=settings.RABBITMQ_HOSTNAME,
    vhost=settings.RABBITMQ_VHOST
)
app = Celery('geoapi', broker=CELERY_CONNECTION_STRING)


@app.task
def hello():
    return "Hello World"

