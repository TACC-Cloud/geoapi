from celery import Celery
from datetime import timedelta
from geoapi.settings import settings


CELERY_CONNECTION_STRING = "amqp://{user}:{pwd}@{hostname}/{vhost}".format(
    user=settings.RABBITMQ_USERNAME,
    pwd=settings.RABBITMQ_PASSWD,
    hostname=settings.RABBITMQ_HOSTNAME,
    vhost=settings.RABBITMQ_VHOST,
)
redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

app = Celery(
    "geoapi",
    backend=redis_url,
    broker=CELERY_CONNECTION_STRING,
    include=["geoapi.tasks"],
)

# Import task modules
app.conf.imports = (
    "geoapi.tasks.raster",
    "geoapi.tasks.point_cloud",
    "geoapi.tasks.streetview",
    "geoapi.tasks.projects",
    "geoapi.tasks.external_data",
    "geoapi.tasks.file_location_check",
)

# Define the queues
app.conf.task_queues = {
    "default": {"exchange": "default", "routing_key": "default"},
    "heavy": {"exchange": "heavy", "routing_key": "heavy"},
}

app.conf.task_default_queue = "default"

# Minimize prefetching (1 extra message per worker child instead of the
# default 4*concurrency to be pulled). Prefetched messages are marked as
# "delivered" by RabbitMQ, which starts the consumer_timeout ack timer
# (default 30min). For long-running tasks (e.g. cog conversion, potree conversion),
# prefetched messages then can sit unacknowledged long enough to trigger the timeout
# and crash the entire worker.
# See: https://www.rabbitmq.com/docs/consumers#acknowledgement-timeout
app.conf.worker_prefetch_multiplier = 1

app.conf.beat_schedule = {
    "refresh_projects_watch_content": {
        "task": "geoapi.tasks.external_data.refresh_projects_watch_content",
        "schedule": timedelta(hours=1),
    },
    "refresh_projects_watch_users": {
        "task": "geoapi.tasks.external_data.refresh_projects_watch_users",
        "schedule": timedelta(minutes=30),
    },
}
