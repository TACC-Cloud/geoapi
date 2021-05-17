import shutil
from pathlib import Path
from typing import List, Optional

from sqlalchemy import desc
from geoapi.models import Project, User, ObservableDataProject
from geoapi.db import db_session
from sqlalchemy.sql import select, text
from sqlalchemy.exc import IntegrityError
from geoapi.services.users import UserService
from geoapi.utils.agave import AgaveUtils, get_system_users
from geoapi.utils.assets import get_project_asset_dir
from geoapi.tasks.external_data import import_from_agave, delete_agave_file
from geoapi.log import logging
from geoapi.exceptions import ApiException, ObservableProjectAlreadyExists

logger = logging.getLogger(__name__)


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
        project.tenant_id = user.tenant_id
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
        folder_name = Path(path).name
        name = systemId + '/' + folder_name

        # TODO: Handle no storage system found
        system = AgaveUtils(user.jwt).systemsGet(systemId)
        proj = Project(
            name=name,
            description=system['description'],
            tenant_id=user.tenant_id,
            system_name=system['description'],
            system_id=systemId
        )

        ProjectsService.export(user,
                               {'system_id': systemId,
                                'path': name,
                                },
                               proj.id,
                               True)

        obs = ObservableDataProject(
            system_id=systemId,
            path=path
        )

        users = get_system_users(proj.tenant_id, user.jwt, systemId)
        logger.info("Updating project:{} to have the following users: {}".format(name, users))
        project_users = [UserService.getOrCreateUser(u, tenant=proj.tenant_id) for u in users]
        proj.users = project_users

        obs.project = proj

        try:
            db_session.add(obs)
            db_session.add(proj)
            db_session.commit()
        except IntegrityError as e:
            db_session.rollback()
            logger.exception("User:{} tried to create an observable project that already exists: '{}'".format(user.username, name))
            raise ObservableProjectAlreadyExists("'{}' project already exists".format(name))
        import_from_agave.apply_async(args=[obs.project.tenant_id, user.id, obs.system_id, obs.path, obs.project_id])

        return proj

    @staticmethod
    def export(user: User,
               data: dict,
               project_id: int) -> Project:
        """
        Save a project UUID file to tapis
        :param user: User
        :param data: dict
        :return: None
        """
        link = data['link']

        current_project = ProjectsService.get(project_id=project_id)

        if link:
            system = AgaveUtils(user.jwt).systemsGet(data['system_id'])

            current_project.system_name = system['description']
            db_session.commit()

        path = data['path']
        file_name = '{}.{}'.format(str(data['file_name']), 'hazmapper')
        if data['file_name'] == '':
            file_name = '{}.{}'.format(str(current_project.uuid), 'hazmapper')

        tmp_system_path = str(current_project.system_path)
        tmp_system_file = str(current_project.system_file)
        tmp_system_id = str(current_project.system_id)

        if not link:
            current_project.system_name = None

        if 'project' not in data['system_id'] and path == '/':
            path = '/' + user.username + '/'

        current_project.system_path = path
        current_project.system_file = file_name
        current_project.system_id = data['system_id']

        db_session.commit()

        file_content = {
            'uuid': str(current_project.uuid)
        }

        AgaveUtils(user.jwt).postFile(data['system_id'],
                                      path,
                                      file_name,
                                      file_content
                                      )

        # If already has a saved file remove it
        if tmp_system_path != 'None':
            delete_agave_file.apply_async(args=[tmp_system_id,
                                                tmp_system_path + '/' + tmp_system_file,
                                                user.id])

        return current_project

    @staticmethod
    def list(user: User) -> List[Project]:
        """
        List a users projects
        :param user: User
        :return: List[Project]
        """
        projects = db_session.query(Project) \
            .join(User.projects)\
            .filter(User.username == user.username)\
            .filter(User.tenant_id == user.tenant_id) \
            .order_by(desc(Project.created))\
            .all()

        return projects

    @staticmethod
    def get(project_id: Optional[int] = None, uuid: Optional[str] = None) -> Project:
        """
        Get the metadata associated with a project
        :param project_id: int
        :param uid: str
        :return: Project
        """
        if project_id is not None:
            return db_session.query(Project).get(project_id)
        elif uuid is not None:
            return db_session.query(Project).filter(Project.uuid == uuid).first()
        raise ValueError("project_id or uid is required")


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
        if query is None:
            query = {}

        # query params
        assetType = query.get("assetType")
        bbox = query.get("bbox")
        startDate = query.get("startDate")
        endDate = query.get("endDate")

        params = {'projectId': projectId,
                  'assetType': assetType,
                  'startDate': startDate,
                  'endDate': endDate}

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
                    'type',        'Feature',
                    'id',          tmp.id,
                    'project_id',  tmp.project_id,
                    'geometry',     ST_AsGeoJSON(the_geom)::json,
                    'created_date', tmp.created_date,
                    'assets',       assets,
                    'styles',       tmp.styles,
                    'properties',   properties
                    )
                ), '[]'::json)
        ) as geojson
        """)

        # The sub select that filters only on this projects ID, filters applied below
        sub_select = select([
            text("""feat.*,  array_remove(array_agg(fa), null) as assets
              from features as feat
              LEFT JOIN feature_assets fa on feat.id = fa.feature_id
             """)
        ]).where(text("project_id = :projectId"))

        if bbox:
            sub_select = sub_select.where(
                text("""feat.the_geom &&
                ST_MakeEnvelope (:bbox_xmin, :bbox_ymin, :bbox_xmax, :bbox_ymax)
                """))
            params.update({"bbox_xmin": bbox[0],
                           "bbox_ymin": bbox[1],
                           "bbox_xmax": bbox[2],
                           "bbox_ymax": bbox[3]})

        if startDate and endDate:
            sub_select = sub_select.where(text("feat.created_date BETWEEN :startDate AND :endDate"))

        if assetType:
            sub_select = sub_select.where(text("fa.asset_type = :assetType"))

        sub_select = sub_select.group_by(text("feat.id")).alias("tmp")
        s = select([select_stmt]).select_from(sub_select)
        result = db_session.execute(s, params)
        out = result.fetchone()
        return out.geojson

    @staticmethod
    def update(projectId: int, data: dict) -> Project:
        """
        Update the metadata associated with a project
        :param projectId: int
        :param data: dict
        :return: Project
        """
        current_project = ProjectsService.get(project_id=projectId)

        current_project.name = data['name']
        if 'description' in data:
            current_project.description = data['description']
        if 'public' in data:
            current_project.public = data['public']
        db_session.commit()

        return current_project

    @staticmethod
    def delete(user: User, projectId: int) -> dict:
        """
        Delete a project and all its Features and assets
        :param projectId: int
        :return:
        """
        proj = db_session.query(Project).get(projectId)

        deleteFile = True if proj.system_path else False

        db_session.delete(proj)
        db_session.commit()

        if deleteFile:
            delete_agave_file.apply_async(args=[proj.system_id,
                                                proj.system_path + '/' + proj.system_file,
                                                user.id])
        assets_folder = get_project_asset_dir(projectId)
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
        user = UserService.getOrCreateUser(username, proj.tenant_id)
        proj.users.append(user)
        db_session.commit()

    @staticmethod
    def getUsers(projectId: int) -> List[User]:
        proj = db_session.query(Project).get(projectId)
        return proj.users

    @staticmethod
    def removeUserFromProject(projectId: int, username: str, ) -> None:
        """
        Remove a user from a Project.
        :param projectId: int
        :param username: str
        :return: None
        """
        proj = db_session.query(Project).get(projectId)
        user = db_session.query(User).filter(User.username == username).first()
        observable_project = db_session.query(ObservableDataProject) \
            .filter(ObservableDataProject.id == projectId).first()

        if user not in proj.users:
            raise ApiException("User is not in project")

        if len(proj.users) == 1:
            raise ApiException("Unable to remove last user of project")

        if observable_project:
            number_of_potential_observers = len([u for u in proj.users if u.jwt])
            if user.jwt and number_of_potential_observers == 1:
                raise ApiException("Unable to remove last user of observable project who can observe file system")

        proj.users.remove(user)
        db_session.commit()
