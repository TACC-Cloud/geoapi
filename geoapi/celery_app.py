from celery import Celery

app = Celery('hello',
             broker='amqp://dev:dev@rabbitmq/dev',
             include=['geoapi.tasks.lidar'])