from typing import IO, Dict

from geoapi.celery_app import app


@app.task()
def process_upload(projectId: int, fileObj: IO, meta: Dict):
    pass
