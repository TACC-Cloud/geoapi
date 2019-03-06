import os
import shutil
from typing import List

from geoapi.settings import settings

from geoapi.models import Project, User
from geoapi.services.users import UserService
from geoapi.db import db_session


class ProjectsService:
    """
    Central location of all interactions with Projects.
    """


    @staticmethod
    def create(data: dict, user: User) -> Project:
        """
        Create a new map project for a user.
        :param data: dict
        :param user: User
        :return: Project
        """

        project = Project(**data)
        project.users.append(user)
        db_session.add(project)
        db_session.commit()
        return project

    @staticmethod
    def list(username: str) -> List[Project]:
        """
        List a users projects
        :param username: str
        :return: List[Project]
        """
        return UserService.projectsForUser(username)

    @staticmethod
    def get(projectId: int) -> Project:
        """
        Get the metadata associated with a project
        :param projectId: int
        :return: Project
        """
        return Project.query.get(projectId)

    @staticmethod
    def getFeatures(projectId: int, query: dict = None) -> object:
        """
        Returns a GeoJSON FeatureCollection of all assets in a project
        :param projectId: int
        :return: GeoJSON
        """
        # TODO: Add filtering somehow...
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
                    'id',         tmp.id, 
                    'geometry',   ST_AsGeoJSON(the_geom)::json,
                    'properties', properties || json_build_object(
                        'assets', assets, 'styles', styles
                        )::jsonb --This merges the properties with extra fields
                    )
                )
        ) as geojson
        FROM (select feat.*, array_remove(array_agg(fa), null) as assets, array_remove(array_agg(fs), null) as styles 
              from features as feat
              left join feature_assets fa on feat.id = fa.feature_id
              LEFT JOIN feature_styles fs on feat.id = fs.feature_id
              where project_id = :projectId
              group by feat.id
              limit 1000
        ) as tmp
        """
        result = db_session.execute(q, {'projectId': projectId})
        out = result.fetchone()
        return out.geojson

    @staticmethod
    def update(projectId: int, data) -> Project:
        pass

    @staticmethod
    def delete(projectId: int) -> dict:
        """
        Delete a project and all its Features and assets
        :param projectId: int
        :return:
        """
        proj = Project.query.get(projectId)
        db_session.delete(proj)
        db_session.commit()
        assets_folder = os.path.join(settings.ASSETS_BASE_DIR, str(projectId))
        try:
            shutil.rmtree(assets_folder)
        except FileNotFoundError:
            pass
        return {"status": "ok"}


    @staticmethod
    def addUserToProject(projectId: int, username: str) -> None:
        """
        Add a user to a project
        :param projectId: int
        :param username: string
        :return:
        """

        # TODO: Add TAS integration
        proj = Project.query.get(projectId)
        user = User.query.filter(User.username == username).first()
        proj.users.append(user)
        db_session.commit()


    @staticmethod
    def getUsers(projectId: int) -> List[User]:
        proj = Project.query.get(projectId)
        return proj.users


    @staticmethod
    def removeUserFromProject(projectId: int, username: str) -> None:
        """
        Remove a user from a Project.
        :param projectId: int
        :param username: str
        :return: None
        """
        proj = db_session.query(Project) \
            .filter(Project.id == projectId).first()
        user = db_session.query(User) \
            .filter(User.username == username).first()
        proj.users.remove(user)
        db_session.commit()

