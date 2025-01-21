from functools import wraps
from flask import abort
from flask import request
from uuid import UUID
from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService
from geoapi.services.features import FeaturesService
from geoapi.services.point_cloud import PointCloudService
from geoapi.utils import jwt_utils
from geoapi.utils.users import is_anonymous, AnonymousUser
from geoapi.db import db_session
from geoapi.log import logger
from geoapi.settings import settings


def jwt_decoder(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = None
        token = None
        try:
            token = jwt_utils.get_jwt(request.headers)
        except ValueError:
            # if not JWT information is provided in header, then this is a guest user
            guest_uuid = request.headers.get("X-Guest-UUID")
            if guest_uuid is None:
                #  Check if in query parameters due to https://tacc-main.atlassian.net/browse/WG-192 and WG-191 */
                guest_uuid = request.args.get("guest_uuid")
            user = AnonymousUser(guest_unique_id=guest_uuid)
        if user is None:
            try:
                decoded = jwt_utils.decode_token(token, verify=not settings.TESTING)
                username = decoded["tapis/username"]
                tenant = decoded["tapis/tenant_id"]
            # Exceptions
            except Exception as e:
                logger.exception(f"There is an issue decoding the JWT: {e}")
                abort(400, f"There is an issue decoding the JWT: {e}")

            user = UserService.getUser(db_session, username, tenant)
            if not user:
                user = UserService.create(
                    db_session, username=username, access_token=token, tenant=tenant
                )
            else:
                # Update the jwt access token
                #   (It is more common that user will be using an auth flow were hazmapper will auth
                #   with geoapi to get the token. BUT we can't assume that as it is also possible that
                #   user just uses geoapi as a service with token generated somewhere else. So we need
                #   to get/update just their access token for these cases)
                UserService.update_access_token(db_session, user, token)
        request.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def check_access_and_get_project(
    current_user, allow_public_use=False, project_id=None, uuid=None
):
    """
    Check if user (authenticated or anonymous) can access a project id and *aborts* if there is no access.
    :param project_id: int
    :param uid: str
    :param current_user: User
    :param allow_public_use: boolean
    :return: project: Project
    """
    # Validate UUID format if uuid is provided
    if uuid is not None:
        try:
            UUID(uuid)
        except ValueError:
            abort(404, "Invalid project UUID")

    proj = (
        ProjectsService.get(db_session, user=current_user, project_id=project_id)
        if project_id
        else ProjectsService.get(db_session, user=current_user, uuid=uuid)
    )
    if not proj:
        abort(404, "No project found")
    if not allow_public_use or not proj.public:
        access = (
            False
            if is_anonymous(current_user)
            else UserService.canAccess(db_session, current_user, proj.id)
        )
        if not access:
            abort(403, "Access denied")
    return proj


def project_permissions(fn):
    """
    Ensure user has access to project.

    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        projectId = kwargs.get("projectId")
        check_access_and_get_project(
            request.current_user, project_id=projectId, allow_public_use=False
        )
        return fn(*args, **kwargs)

    return wrapper


def project_permissions_allow_public(fn):
    """
    Ensure user has access to project or project is public.

    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        projectId = kwargs.get("projectId")
        check_access_and_get_project(
            request.current_user, project_id=projectId, allow_public_use=True
        )
        return fn(*args, **kwargs)

    return wrapper


def project_admin_or_creator_permissions(fn):
    """
    Ensure user has admin-level access to project or is project's creator.

    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        projectId = kwargs.get("projectId")
        check_access_and_get_project(
            request.current_user, project_id=projectId, allow_public_use=False
        )
        if not UserService.is_admin_or_creator(
            db_session, request.current_user, projectId
        ):
            abort(403, "Access denied")
        return fn(*args, **kwargs)

    return wrapper


def project_feature_exists(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        projectId = kwargs.get("projectId")
        proj = ProjectsService.get(db_session, projectId)
        if not proj:
            abort(404, "No project found")
        featureId = kwargs.get("featureId")
        feature = FeaturesService.get(db_session, featureId)
        if not feature:
            abort(404, "No feature found!")
        if feature.project_id != projectId:
            abort(404, "Feature not part of project")
        return fn(*args, **kwargs)

    return wrapper


def project_point_cloud_exists(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        projectId = kwargs.get("projectId")
        proj = ProjectsService.get(db_session, projectId)
        if not proj:
            abort(404, "No project found")
        pointCloudId = kwargs.get("pointCloudId")
        point_cloud = PointCloudService.get(db_session, pointCloudId)
        if not point_cloud:
            abort(404, "No point cloud found!")
        if point_cloud.project_id != projectId:
            abort(404, "Point cloud not part of project")
        return fn(*args, **kwargs)

    return wrapper


def project_point_cloud_not_processing(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        point_cloud_id = kwargs.get("pointCloudId")
        point_cloud = PointCloudService.get(db_session, point_cloud_id)
        if point_cloud.task and point_cloud.task.status not in ["FINISHED", "FAILED"]:
            logger.info(f"point cloud:{point_cloud_id} is not in terminal state")
            abort(404, "Point cloud is currently being updated")
        return fn(*args, **kwargs)

    return wrapper


def not_anonymous(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if is_anonymous(request.current_user):
            abort(403, "Access denied")
        return fn(*args, **kwargs)

    return wrapper
