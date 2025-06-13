from uuid import UUID
from typing import TYPE_CHECKING
from litestar.connection import ASGIConnection
from litestar.handlers.base import BaseRouteHandler
from litestar.exceptions import HTTPException
from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService
from geoapi.services.features import FeaturesService
from geoapi.services.point_cloud import PointCloudService
from geoapi.utils import jwt_utils
from geoapi.utils.users import is_anonymous, AnonymousUser
from geoapi.log import logger
from geoapi.settings import settings


if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def jwt_decoder_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Middleware to decode JWT and set the current user in the request."""

    db_session: "Session" = connection.scope.get("db_session")

    user = None
    try:
        # Get JWT from header first
        token = jwt_utils.get_jwt(connection.headers)
    except ValueError:
        # Try cookie fallback; Cookies are being used pre-WG-472 for
        # nginx-related access check of /assets
        token = connection.cookies.get("X-Tapis-Token")

    # If still no token, check for guest UUID
    if not token:
        # if JWT is not provided in header/cookie, then this is a guest user
        # and if hazmapper/taggit, a guest uuid is provided in the header
        guest_uuid = connection.headers.get("X-Guest-UUID")
        user = AnonymousUser(guest_unique_id=guest_uuid)
    else:
        try:
            decoded = jwt_utils.decode_token(token, verify=not settings.TESTING)
            username = decoded["tapis/username"]
            tenant = decoded["tapis/tenant_id"]
        # Exceptions
        except Exception as e:
            logger.exception("There is an issue decoding the JWT")
            raise HTTPException(
                status_code=400, detail=f"There is an issue decoding the JWT: {e}"
            ) from e

        user = UserService.getUser(db_session, username, tenant)
        if not user:
            user = UserService.create(
                db_session, username=username, access_token=token, tenant=tenant
            )
        else:
            # Update the jwt access token
            UserService.update_access_token(db_session, user, token)

    connection.user = user


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
            raise HTTPException(status_code=404, detail="Invalid project UUID") from exc

    proj = (
        ProjectsService.get(db_session, user=current_user, project_id=project_id)
        if project_id
        else ProjectsService.get(db_session, user=current_user, uuid=uuid)
    )
    if not proj:
        raise HTTPException(status_code=404, detail="No project found")
    if not allow_public_use or not proj.public:
        access = (
            False
            if is_anonymous(current_user)
            else UserService.canAccess(db_session, current_user, proj.id)
        )
        if not access:
            raise HTTPException(status_code=403, detail="Access denied")
    return proj


def project_permissions_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """
    Middleware to ensure user has access to project.

    This is used in the ASGI app to check permissions before processing the request.
    """
    db_session: "Session" = connection.scope.get("db_session")
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
    db_session: "Session" = connection.scope.get("db_session")
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
    db_session: "Session" = connection.scope.get("db_session")
    project_id = connection.path_params["project_id"]

    check_access_and_get_project(
        connection.user,
        db_session=db_session,
        project_id=project_id,
        allow_public_use=False,
    )
    if not UserService.is_admin_or_creator(db_session, connection.user, project_id):
        raise HTTPException(status_code=403, detail="Access denied")


def project_feature_exists_guard(
    connection: ASGIConnection, _: BaseRouteHandler
) -> None:
    """
    Middleware to ensure feature exists in project.

    This is used in the ASGI app to check permissions before processing the request.
    """
    db_session: "Session" = connection.scope.get("db_session")
    project_id = connection.path_params["project_id"]
    feature_id = connection.path_params["featureId"]

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
    db_session: "Session" = connection.scope.get("db_session")
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
    db_session: "Session" = connection.scope.get("db_session")
    point_cloud_id = connection.path_params["point_cloud_id"]

    point_cloud = PointCloudService.get(db_session, point_cloud_id)
    if point_cloud.task and point_cloud.task.status not in ["FINISHED", "FAILED"]:
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
        raise HTTPException(status_code=403, detail="Access denied")
