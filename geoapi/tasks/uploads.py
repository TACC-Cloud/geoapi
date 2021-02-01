from typing import IO, Dict

from geoapi.celery_app import app
from geoapi.models.feature import Feature, FeatureAsset
from geoapi.services.features import FeaturesService
from geoapi.services.images import ImageService
from geoapi.services.videos import VideoService


@app.task()
def process_upload(projectId: int, fileObj: IO, meta: Dict):
    pass
