from geoapi.models import Project, User, Feature
from geoapi.db import db_session
from typing import List
from geoapi.services.features import FeatureService
from geoapi.services.images import ImageService


"""
SELECT json_build_object(
    'type',       'Feature',
    'id',         gid,
    'geometry',   ST_AsGeoJSON(geom)::json,
    'properties', json_build_object(
        'feat_type', feat_type,
        'feat_area', ST_Area(geom)::geography
     )
 )
 FROM input_table;
"""

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
    def addImage(projectId: int, fileObj) -> Feature:
        print(fileObj)
        imdata = ImageService.processImage(fileObj)
        print(imdata)
    @staticmethod
    def addGeoJSON(projectId: int, feature: object) -> Feature:
        print(projectId)
        print(feature)
        # task.geometry = ST_SetSRID(ST_GeomFromGeoJSON(task_geojson), 4326)


    @staticmethod
    def addLidarData(projectID: int, layergroupId=None) -> Feature:
        pass