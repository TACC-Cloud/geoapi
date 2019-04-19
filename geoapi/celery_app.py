from celery import Celery

app = Celery('hello', broker='amqp://dev:dev@rabbitmq/dev')


@app.task
def hello():
    return "Hello World"

