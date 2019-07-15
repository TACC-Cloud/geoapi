import os
import shutil
from typing import List

from geoapi.settings import settings

from geoapi.models import Project, User, ObservableDataProject
from geoapi.db import db_session
from sqlalchemy.sql import select, func, text, and_
from sqlalchemy.exc import IntegrityError
from geoapi.utils.agave import AgaveUtils


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
    def createRapidProject(data: dict, user: User) -> Project:
        """
        Creates a project from a storage system for the RAPID recon projects in Designsafe
        :param data: dict
        :param user: User
        :return: Project
        """
        systemId = data["system_id"]
        path = data["path"]


        # TODO: Handle no storage system found
        system = AgaveUtils(user.jwt).systemsGet(systemId)
        proj = Project(
            name=system["description"],
            description=system["description"]
        )
        obs = ObservableDataProject(
            system_id=system["id"],
            path=path
        )
        # roles = client.systems.listRoles(systemId=system.id)
        # print(roles)
        obs.project = proj
        proj.users.append(user)
        try:
            db_session.add(obs)
            db_session.add(proj)
            db_session.commit()
        except IntegrityError as e:
            raise e
        return proj


    @staticmethod
    def list(user: User) -> List[Project]:
        """
        List a users projects
        :param username: str
        :return: List[Project]
        """
        return user.projects

    @staticmethod
    def get(projectId: int) -> Project:
        """
        Get the metadata associated with a project
        :param projectId: int
        :return: Project
        """
        return db_session.query(Project).get(projectId)

    @staticmethod
    def getFeatures(projectId: int, query: dict = None) -> object:
        """
        Returns a GeoJSON FeatureCollection of all assets in a project

        This is the main query

        SELECT  json_build_object(
            'type', 'FeatureCollection',
            'crs',  json_build_object(
                'type',      'name',
                'properties', json_build_object(
                    'name', 'EPSG:4326'
                )
            ),
            'features', coalesce(json_agg(
                json_build_object(
                    'type',       'Feature',
                    'id',         tmp.id,
                    'geometry',   ST_AsGeoJSON(the_geom)::json,
                     'assets', assets,
                     'styles', styles,
                    'properties', properties
                ), '[]'::json)
        ) as geojson
        FROM (select feat.*, array_remove(array_agg(fa), null) as assets, array_remove(array_agg(fs), null) as styles
              from features as feat
              LEFT JOIN feature_assets fa on feat.id = fa.feature_id
              LEFT JOIN feature_styles fs on feat.id = fs.feature_id
              where project_id = :projectId
              group by feat.id
        ) as tmp
        :param projectId: int
        :return: GeoJSON
        """

        select_stmt = text("""
        json_build_object(
            'type', 'FeatureCollection',
            'crs',  json_build_object(
                'type',      'name',
                'properties', json_build_object(
                    'name', 'EPSG:4326'
                )
            ),
            'features', coalesce(json_agg(
                json_build_object(
                    'type',       'Feature',
                    'id',         tmp.id,
                    'geometry',   ST_AsGeoJSON(the_geom)::json,
                    'created_date', tmp.created_date,
                    'assets', assets, 
                    'styles', styles, 
                    'properties', properties
                    )
                ), '[]'::json)
        ) as geojson
        """)

        sub_select = select([
            text("""feat.*,  array_remove(array_agg(fa), null) as assets, array_remove(array_agg(fs), null) as styles 
              from features as feat
              LEFT JOIN feature_assets fa on feat.id = fa.feature_id
              LEFT JOIN feature_styles fs on feat.id = fs.feature_id""")
        ]).where(text("project_id = :projectId")).group_by(text("feat.id")).alias("tmp")

        if query.get("bbox"):
            print(query)
            # TODO: implement bounding box filters

        s = select([select_stmt]).select_from(sub_select)
        result = db_session.execute(s, {'projectId': projectId})
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
        proj = db_session.query(Project).get(projectId)
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
        proj = db_session.query(Project).get(projectId)
        user = db_session.query(User).filter(User.username == username).first()
        proj.users.append(user)
        db_session.commit()


    @staticmethod
    def getUsers(projectId: int) -> List[User]:
        proj = db_session.query(Project).get(projectId)
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

