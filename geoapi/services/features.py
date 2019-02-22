from geoapi.models import Project, User, Feature, FeatureAsset
from geoapi.db import db_session
from typing import List
from PIL import Image
import PIL.ExifTags

class FeatureService:

    @staticmethod
    def getFeature(featureId: int)-> Feature:
        return Feature.query.filter(Feature.id == featureId).first()


    @staticmethod
    def query(q) -> List[Feature]:
        pass

    @staticmethod
    def delete(featureId: int) -> None:
        # TODO: remove any assets tied to the feature also
        pass

    @staticmethod
    def setProperties(featureId: int, props: dict) -> Feature:
        feat = Feature.query.get(featureId)
        # TODO: Throw assert if not found?
        feat.properties = props
        db_session.commit()
        return feat
