
from uuid import UUID
from typing import TYPE_CHECKING
from litestar.connection import ASGIConnection
from litestar.handlers.base import BaseRouteHandler
from litestar.exceptions import (
    HTTPException,
    NotAuthorizedException,
    PermissionDeniedException,
    NotFoundException,
)
from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService
from geoapi.services.features import FeaturesService
from geoapi.services.point_cloud import PointCloudService
from geoapi.utils.users import is_anonymous
from geoapi.log import logger
from geoapi.db import sqlalchemy_config


if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def check_access_and_get_project(
    current_user,
    db_session: "Session",
    allow_public_use=False,
    project_id=None,
    uuid=None,
):
    """
    Check if user (authenticated or anonymous) can access a project id and *aborts* if there is no access.
    :param project_id: int
    :param uuid: str
    :param current_user: User
    :param allow_public_use: boolean
    :return: project: Project
    """
    # Validate UUID format if uuid is provided
    if uuid is not None:
        try:
            UUID(uuid)
        except ValueError as exc:
            raise NotFoundException("Invalid project UUID") from exc
    proj = (
        ProjectsService.get(db_session, user=current_user, project_id=project_id)
        if project_id
        else ProjectsService.get(db_session, user=current_user, uuid=uuid)
    )
    if not proj:
        raise NotFoundException("No project found")
    if not allow_public_use or not proj.public:
        if is_anonymous(current_user):
            raise NotAuthorizedException("Must be logged in to access project")

        if not UserService.canAccess(db_session, current_user, proj.id):
            raise PermissionDeniedException("Access denied")
    return proj


def project_permissions_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """
    Middleware to ensure user has access to project.

    This is used in the ASGI app to check permissions before processing the request.
    """
    db_session: "Session" = sqlalchemy_config.provide_session(
        connection.app.state, connection.scope
    )
    project_id = connection.path_params["project_id"]

    check_access_and_get_project(
        connection.user,
        db_session=db_session,
        project_id=project_id,
        allow_public_use=False,
    )


def project_permissions_allow_public_guard(
    connection: ASGIConnection, _: BaseRouteHandler
) -> None:
    """
    Middleware to ensure user has access to project or project is public.

    This is used in the ASGI app to check permissions before processing the request.
    """
    db_session: "Session" = sqlalchemy_config.provide_session(
        connection.app.state, connection.scope
    )
    project_id = connection.path_params["project_id"]

    check_access_and_get_project(
        connection.user,
        db_session=db_session,
        project_id=project_id,
        allow_public_use=True,
    )

def project_admin_or_creator_permissions_guard(
    connection: ASGIConnection, _: BaseRouteHandler
) -> None:
    """
    Middleware to ensure user has admin-level access to project or is project's creator.

    This is used in the ASGI app to check permissions before processing the request.
    """
    db_session: "Session" = sqlalchemy_config.provide_session(
        connection.app.state, connection.scope
    )
    project_id = connection.path_params["project_id"]

    check_access_and_get_project(
        connection.user,
        db_session=db_session,
        project_id=project_id,
        allow_public_use=False,
    )
    if not UserService.is_admin_or_creator(db_session, connection.user, project_id):
        raise PermissionDeniedException("Must be project admin or creator")


def project_feature_exists_guard(
    connection: ASGIConnection, _: BaseRouteHandler
) -> None:
    """
    Middleware to ensure feature exists in project.

    This is used in the ASGI app to check permissions before processing the request.
    """
    db_session: "Session" = sqlalchemy_config.provide_session(
        connection.app.state, connection.scope
    )
    project_id = connection.path_params["project_id"]
    feature_id = connection.path_params["feature_id"]

    proj = ProjectsService.get(db_session, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="No project found")

    feature = FeaturesService.get(db_session, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="No feature found!")
    if feature.project_id != project_id:
        raise HTTPException(status_code=404, detail="Feature not part of project")


def project_point_cloud_exists_guard(
    connection: ASGIConnection, _: BaseRouteHandler
) -> None:
    """
    Middleware to ensure point cloud exists in project.

    This is used in the ASGI app to check permissions before processing the request.
    """
    db_session: "Session" = sqlalchemy_config.provide_session(
        connection.app.state, connection.scope
    )
    project_id = connection.path_params["project_id"]
    point_cloud_id = connection.path_params["point_cloud_id"]

    proj = ProjectsService.get(db_session, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="No project found")

    point_cloud = PointCloudService.get(db_session, point_cloud_id)
    if not point_cloud:
        raise HTTPException(status_code=404, detail="No point cloud found!")
    if point_cloud.project_id != project_id:
        raise HTTPException(status_code=404, detail="Point cloud not part of project")


def project_point_cloud_not_processing_guard(
    connection: ASGIConnection, _: BaseRouteHandler
) -> None:
    """
    Middleware to ensure point cloud is not currently being processed.

    This is used in the ASGI app to check permissions before processing the request.
    """
    db_session: "Session" = sqlalchemy_config.provide_session(
        connection.app.state, connection.scope
    )
    point_cloud_id = connection.path_params["point_cloud_id"]

    point_cloud = PointCloudService.get(db_session, point_cloud_id)
    if point_cloud.task and point_cloud.task.status not in [
        "COMPLETED",
        "FINISHED",
        "FAILED",
    ]:
        logger.info(f"point cloud:{point_cloud_id} is not in terminal state")
        raise HTTPException(
            status_code=404, detail="Point cloud is currently being updated"
        )


def not_anonymous_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """
    Middleware to ensure user is not anonymous.

    This is used in the ASGI app to check permissions before processing the request.
    """
    if is_anonymous(connection.user):
        raise NotAuthorizedException("Must be logged in to access this resource")
