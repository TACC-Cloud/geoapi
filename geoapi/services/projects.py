import uuid
import json
import os
import pathlib
from typing import List
import shapely
from shapely.geometry import Point
from geoalchemy2.shape import from_shape, to_shape
import geojson

from geoapi.models import Project, User, Feature
from geoapi.db import db_session
from geoapi.services.features import FeatureService
from geoapi.services.images import ImageService
from geoapi.exceptions import InvalidGeoJSON
from geoapi.settings import settings

class ProjectsService:

    @staticmethod
    def create(data: dict, user: User) -> Project:
        project = Project(**data)
        project.users.append(user)
        db_session.add(project)
        db_session.commit()
        return project

    @staticmethod
    def list(username: str) -> List[Project]:
        u = db_session.query(User).filter(User.username == username).first()
        if not u:
            return []
        return u.projects

    @staticmethod
    def get(projectId: int) -> Project:

        return db_session.query(Project)\
            .filter(Project.id == projectId).first()


    @staticmethod
    def getFeatures(projectId: int) -> object:
        q = """
        SELECT  json_build_object(
            'type', 'FeatureCollection',
            'crs',  json_build_object(
                'type',      'name', 
                'properties', json_build_object(
                    'name', 'EPSG:4326'  
                )
            ), 
            'features', json_agg(
                json_build_object(
                    'type',       'Feature',
                    'id',         id, 
                    'geometry',   ST_AsGeoJSON(the_geom)::json,
                    'properties', properties || json_build_object(
                        'image_uuid', image_uuid, 'collection', collection)::jsonb --This merges the properties with extra fields
                    )
                )
        ) as geojson
        FROM features
        where project_id = :projectId;
        """
        result = db_session.execute(q, {'projectId': projectId})
        out = result.fetchone()
        return out.geojson

    @staticmethod
    def update(projectId: int, data) -> Project:
        pass

    @staticmethod
    def delete(projectId: int) -> None:
        db_session.query(Project) \
            .filter(Project.id == projectId).delete()
        db_session.commit()

    @staticmethod
    def addUserToProject(projectId: int, username: str) -> None:
        proj = db_session.query(Project) \
            .filter(Project.id == projectId).first()
        user = db_session.query(User) \
                .filter(User.username == username).first()
        proj.users.append(user)
        db_session.commit()

    @staticmethod
    def removeUserFromProject(projectId: int, username: str) -> None:
        proj = db_session.query(Project) \
            .filter(Project.id == projectId).first()
        user = db_session.query(User) \
            .filter(User.username == username).first()
        proj.users.remove(user)
        db_session.commit()

    @staticmethod
    def addImage(projectId: int, fileObj, metadata: dict) -> Feature:
        imdata = ImageService.processImage(fileObj)
        point = Point(imdata.coordinates)
        f = Feature()
        f.project_id = projectId
        f.the_geom = from_shape(point, srid=4326)
        f.image_uuid = uuid.uuid4()
        f.properties = metadata
        pathlib.Path(os.path.join(settings.ASSETS_BASE_DIR, str(projectId))).mkdir(parents=True, exist_ok=True)
        imdata.thumb.save(os.path.join(settings.ASSETS_BASE_DIR, str(projectId), str(f.image_uuid)+".thumb"), "JPEG")
        imdata.resized.save(os.path.join(settings.ASSETS_BASE_DIR, str(projectId), str(f.image_uuid)), "JPEG")

        db_session.add(f)
        db_session.commit()

    @staticmethod
    def addGeoJSON(projectId: int, feature: dict) -> Feature:
        try:
            data = geojson.loads(json.dumps(feature))
        except ValueError:
            raise InvalidGeoJSON

        if data["type"] == "Feature":
            feat = Feature.fromGeoJSON(data)
            feat.project_id = projectId
            db_session.add(feat)
        elif data["type"] == "FeatureCollection":
            fc = geojson.FeatureCollection(data)
            for feature in fc.features:
                feat = Feature.fromGeoJSON(feature)
                feat.project_id = projectId
                db_session.add(feat)
        else:
            raise InvalidGeoJSON
        db_session.commit()
        return True

    @staticmethod
    def addLidarData(projectID: int) -> Feature:
        pass