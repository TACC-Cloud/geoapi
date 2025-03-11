from celery import Celery
from datetime import timedelta
from geoapi.settings import settings


CELERY_CONNECTION_STRING = "amqp://{user}:{pwd}@{hostname}/{vhost}".format(
    user=settings.RABBITMQ_USERNAME,
    pwd=settings.RABBITMQ_PASSWD,
    hostname=settings.RABBITMQ_HOSTNAME,
    vhost=settings.RABBITMQ_VHOST,
)

app = Celery(
    "hello", backend="rpc", broker=CELERY_CONNECTION_STRING, include=["geoapi.tasks"]
)

# Define the queues
app.conf.task_queues = {
    "default": {"exchange": "default", "routing_key": "default"},
    "heavy": {"exchange": "heavy", "routing_key": "heavy"},
}

app.conf.task_default_queue = "default"

app.conf.beat_schedule = {
    "refresh_projects_watch_content": {
        "task": "geoapi.tasks.external_data.refresh_projects_watch_content",
        "schedule": timedelta(hours=1),
    },
    "refresh_projects_watch_users": {
        "task": "geoapi.tasks.external_data.refresh_projects_watch_users",
        "schedule": timedelta(minutes=30),
    },
    "cleanup_expired_sessions": {
        "task": "geoapi.tasks.flask_sessions.cleanup_expired_sessions",
        "schedule": timedelta(days=1),
    },
}
