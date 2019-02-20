from geoapi.models import Project, User, Feature, FeatureAsset
from geoapi.db import db_session
from typing import List
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

class FeatureService:

    @staticmethod
    def getFeature(featureId: int)-> Feature:
        return Feature.query.filter(Feature.id == featureId).first()

    @staticmethod
    def createFeatureFromImage(fileObj) -> Feature:
        image = PIl.open(fileObj)
        info = image._getexif()
        print(info)

    @staticmethod
    def query(q) -> List[Feature]:
        pass

    @staticmethod
    def delete(featureId: int) -> None:
        # TODO: remove any assets tied to the feature also
        pass
