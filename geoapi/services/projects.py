from typing import List, Optional

from sqlalchemy import desc, exists
from geoapi.models import Project, ProjectUser, User
from sqlalchemy.sql import select, text
from geoapi.services.users import UserService
from geoapi.utils.external_apis import TapisUtils, get_system_users
from geoapi.utils.users import is_anonymous
from geoapi.tasks.external_data import import_from_tapis
from geoapi.tasks.projects import remove_project_assets
from geoapi.log import logger
from geoapi.exceptions import (
    ApiException,
    GetUsersForProjectNotSupported,
    ProjectSystemPathWatchFilesAlreadyExists,
)
from geoapi.custom import custom_on_project_creation, custom_on_project_deletion


class ProjectsService:
    """
    Central location of all interactions with Projects.
    """

    @staticmethod
    def create(database_session, data: dict, user: User) -> Project:
        """
        Create a new map project for a user.
        :param data: dict
        :param user: User
        :return: Project
        """
        # Check that a storage system is there
        if data.get("system_id"):
            TapisUtils(database_session, user).systemsGet(data.get("system_id"))

        system_id = data.get("system_id")
        system_path = data.get("system_path")

        # Check that there is no other matching projects if watch_content is True
        if data.get(
            "watch_content"
        ) and ProjectsService.is_project_watching_content_on_system_path(
            database_session, system_id, system_path
        ):
            logger.exception(
                f"User:{user.username} tried to create a project with watch_content although there is "
                f"a project for that  system_id={system_id} and system_path={system_path}"
            )
            raise ProjectSystemPathWatchFilesAlreadyExists(
                f"'{system_id}/{system_path}' project already exists"
            )

        project = Project(**data)
        project.tenant_id = user.tenant_id
        project.users.append(user)

        database_session.add(project)
        database_session.commit()

        # Now after the above commit, we have project_users,
        # and we can now mark the creator.
        for project_user in project.project_users:
            if project_user.user_id == user.id:
                project_user.creator = True
                break

        database_session.add(project)
        database_session.commit()

        # Run any custom on-project-creation actions
        if user.tenant_id.upper() in custom_on_project_creation:
            custom_on_project_creation[user.tenant_id.upper()](
                database_session, user, project
            )

        if project.system_id:
            try:
                system_users = get_system_users(
                    database_session, user, project.system_id
                )
                logger.info(
                    f"Initial update of project_id:{project.id} system_id:{project.system_id} "
                    f"system_path:{project.system_path} to have the following users: {system_users}"
                )
                users = [
                    UserService.getOrCreateUser(
                        database_session, user.username, project.tenant_id
                    )
                    for user in system_users
                ]
                project.users = users

                if system_users:
                    # Initialize the admin status
                    users_dict = {user.username: user for user in system_users}
                    for project_user in project.project_users:
                        project_user.admin = users_dict[
                            project_user.user.username
                        ].admin
                database_session.add(project)
                database_session.commit()
            except GetUsersForProjectNotSupported:
                logger.info(
                    f"Not getting users for project_id:{project.id} system:{project.system_id}"
                )

        if project.watch_content:
            import_from_tapis.apply_async(
                args=[
                    project.tenant_id,
                    user.id,
                    project.system_id,
                    project.system_path,
                    project.id,
                ]
            )
        setattr(project, "deletable", True)
        return project

    @staticmethod
    def list(database_session, user: User) -> List[Project]:
        """
        List a users projects
        :param user: User
        :return: List[Project]
        """
        projects_and_project_user = (
            database_session.query(Project, ProjectUser)
            .join(ProjectUser)
            .filter(ProjectUser.user_id == user.id)
            .order_by(desc(Project.created))
            .all()
        )
        for p, u in projects_and_project_user:
            setattr(p, "deletable", u.admin or u.creator)

        return [p for p, _ in projects_and_project_user]

    @staticmethod
    def get(
        database_session,
        project_id: Optional[int] = None,
        uuid: Optional[str] = None,
        user: User = None,
    ) -> Project:
        """
        Get the metadata associated with a project
        :param project_id: int
        :param uid: str
        :return: Project
        """
        if project_id is not None:
            project = database_session.get(Project, project_id)
        elif uuid is not None:
            project = (
                database_session.query(Project).filter(Project.uuid == uuid).first()
            )
        else:
            raise ValueError("project_id or uid is required")

        if project and user and not is_anonymous(user):
            project_user = (
                database_session.query(ProjectUser)
                .filter(ProjectUser.project_id == project.id)
                .filter(ProjectUser.user_id == user.id)
                .one_or_none()
            )
            if project_user:
                setattr(
                    project, "deletable", project_user.admin or project_user.creator
                )
        return project

    @staticmethod
    def getFeatures(database_session, projectId: int, query: dict = None) -> object:
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

        params = {"projectId": projectId, "startDate": startDate, "endDate": endDate}

        assetTypes = assetType.split(",") if assetType else []
        assetQueries = []

        for asset in assetTypes:
            if asset:
                params[asset] = asset
                assetQueries.append(
                    "fa is null"
                    if asset == "no_asset_vector"
                    else "fa.asset_type = :" + asset
                )

        select_stmt = text(
            """
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
        """
        )

        # The sub select that filters only on this projects ID, filters applied below
        sub_select = select(
            text(
                """feat.*,  array_remove(array_agg(fa), null) as assets
              from features as feat
              LEFT JOIN feature_assets fa on feat.id = fa.feature_id
             """
            )
        ).where(text("project_id = :projectId"))

        if bbox:
            sub_select = sub_select.where(
                text(
                    """feat.the_geom &&
                ST_MakeEnvelope (:bbox_xmin, :bbox_ymin, :bbox_xmax, :bbox_ymax)
                """
                )
            )
            params.update(
                {
                    "bbox_xmin": bbox[0],
                    "bbox_ymin": bbox[1],
                    "bbox_xmax": bbox[2],
                    "bbox_ymax": bbox[3],
                }
            )

        if startDate and endDate:
            sub_select = sub_select.where(
                text("feat.created_date BETWEEN :startDate AND :endDate")
            )

        if len(assetQueries):
            sub_select = sub_select.where(text("(" + " OR ".join(assetQueries) + ")"))

        sub_select = sub_select.group_by(text("feat.id")).subquery("tmp")
        s = select(select_stmt).select_from(sub_select)
        result = database_session.execute(s, params)
        out = result.fetchone()
        return out.geojson

    @staticmethod
    def update(database_session, projectId: int, data: dict) -> Project:
        """
        Update the metadata associated with a project.

        Only `name`, `description` and `public` can be updated.

        :param projectId: int
        :param data: dict
        :return: Project
        """
        project = ProjectsService.get(
            database_session=database_session, project_id=projectId
        )

        project.name = data.get("name", project.name)
        project.description = data.get("description", project.description)
        project.public = data.get("public", project.public)

        database_session.commit()

        return project

    @staticmethod
    def delete(database_session, user: User, projectId: int) -> dict:
        """
        Delete a project and all its Features and assets
        :param projectId: int
        :return:
        """
        # Run any custom on-project-deletion actions
        if user.tenant_id.upper() in custom_on_project_deletion:
            project = (
                database_session.query(Project).filter(Project.id == projectId).one()
            )
            custom_on_project_deletion[user.tenant_id.upper()](
                database_session, user, project
            )

        # TODO move the database remove call to celery (https://tacc-main.atlassian.net/browse/WG-235)
        database_session.query(Project).filter(Project.id == projectId).delete()
        database_session.commit()

        remove_project_assets.apply_async(args=[projectId])

        return {"status": "ok"}

    @staticmethod
    def addUserToProject(
        database_session, projectId: int, username: str, admin: bool
    ) -> None:
        """
        Add a user to a project
        :param projectId: int
        :param username: string
        :param admin: bool
        :return:
        """

        project = database_session.get(Project, projectId)
        user = UserService.getOrCreateUser(
            database_session, username, project.tenant_id
        )
        project.users.append(user)
        database_session.commit()

        project_user = (
            database_session.query(ProjectUser)
            .filter(ProjectUser.project_id == projectId)
            .filter(ProjectUser.user_id == user.id)
            .one()
        )
        project_user.admin = admin
        database_session.commit()

    @staticmethod
    def getUsers(database_session, projectId: int) -> List[User]:
        project = database_session.get(Project, projectId)
        return project.users

    @staticmethod
    def getUser(database_session, projectId: int, username: str) -> User:
        proj = ProjectsService.get(database_session, projectId)
        user = UserService.getUser(database_session, username, proj.tenant_id)
        return user

    @staticmethod
    def removeUserFromProject(database_session, projectId: int, username: str) -> None:
        """
        Remove a user from a Project.
        :param projectId: int
        :param username: str
        :return: None
        """
        project = database_session.get(Project, projectId)
        user = database_session.query(User).filter(User.username == username).first()

        if user not in project.users:
            raise ApiException("User is not in project")

        if len(project.users) == 1:
            raise ApiException("Unable to remove last user of project")

        if project.watch_content or project.watch_users:
            number_of_potential_observers = len(
                [user for user in project.users if user.jwt]
            )
            if user.jwt and number_of_potential_observers == 1:
                raise ApiException(
                    "Unable to remove last user of project who can observe file system or users"
                )

        project.users.remove(user)
        database_session.commit()

    @staticmethod
    def is_project_watching_content_on_system_path(
        database_session, system_id, system_path
    ) -> bool:
        """
        Check if any project is watching content at the specified system path.
        """
        return database_session.query(
            exists().where(
                Project.system_id == system_id,
                Project.system_path == system_path,
                Project.watch_content,
            )
        ).scalar()
