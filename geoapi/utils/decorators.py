
from functools import wraps
from flask import abort
from flask import request
import jwt
from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService
from geoapi.services.features import FeaturesService
from geoapi.services.point_cloud import PointCloudService
from geoapi.services.streetview import StreetviewService
from geoapi.settings import settings
from geoapi.utils import jwt_utils
from geoapi.log import logger
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import base64


class AnonymousUser:
    username = "Guest"


def is_anonymous(user):
    return isinstance(user, AnonymousUser)


def get_pub_key():
    pkey = base64.b64decode(settings.JWT_PUB_KEY)
    pub_key = serialization.load_der_public_key(pkey,
                                                backend=default_backend())
    return pub_key


def jwt_decoder(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        pub_key = get_pub_key()
        user = None
        try:
            jwt_header_name, token, tenant = jwt_utils.jwt_tenant(request.headers)
        except ValueError:
            # TODO consider using something else like Flask-Login
            # if not JWT information is provided in header, then this is a guest user
            user = AnonymousUser()
        if user is None:
            try:
                # TODO: validate token
                decoded = jwt.decode(token, pub_key, verify=False)
                username = decoded["http://wso2.org/claims/enduser"]
                # remove ant @carbon.super or other nonsense, the tenant
                # we get from the header anyway
                username = username.split("@")[0]
            except Exception as e:
                logger.exception(e)
                abort(400, 'could not decode JWT')

            user = UserService.getUser(username, tenant)
            if not user:
                user = UserService.create(username=username, jwt=token, tenant=tenant)
            # In case the JWT was updated for some reason, reset the jwt
            UserService.setJWT(user, token)
        request.current_user = user
        return fn(*args, **kwargs)
    return wrapper


def check_access_and_get_project(current_user, allow_public_use=False, project_id=None, uuid=None):
    """
    Check if user (authenticated or anonymous) can access a project id and *aborts* if there is no access.
    :param project_id: int
    :param uid: str
    :param current_user: User
    :param allow_public_use: boolean
    :return: project: Project
    """
    proj = ProjectsService.get(project_id=project_id) if project_id else ProjectsService.get(uuid=uuid)
    if not proj:
        abort(404, "No project found")
    if not allow_public_use or not proj.public:
        access = False if is_anonymous(current_user) else UserService.canAccess(current_user, proj.id)
        if not access:
            abort(403, "Access denied")
    return proj


def project_permissions(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        projectId = kwargs.get("projectId")
        check_access_and_get_project(request.current_user, project_id=projectId, allow_public_use=False)
        return fn(*args, **kwargs)
    return wrapper


def project_permissions_allow_public(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        projectId = kwargs.get("projectId")
        check_access_and_get_project(request.current_user, project_id=projectId, allow_public_use=True)
        return fn(*args, **kwargs)
    return wrapper


def project_feature_exists(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        projectId = kwargs.get("projectId")
        proj = ProjectsService.get(projectId)
        if not proj:
            abort(404, "No project found")
        featureId = kwargs.get("featureId")
        feature = FeaturesService.get(featureId)
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
        proj = ProjectsService.get(projectId)
        if not proj:
            abort(404, "No project found")
        pointCloudId = kwargs.get("pointCloudId")
        point_cloud = PointCloudService.get(pointCloudId)
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
        point_cloud = PointCloudService.get(point_cloud_id)
        if point_cloud.task \
                and point_cloud.task.status not in ["FINISHED", "FAILED"]:
            logger.info("point cloud:{} is not in terminal state".format(
                point_cloud_id))
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


def streetview_service_permissions(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        service = kwargs.get("service")
        streetview_resource_service = StreetviewService.getByService(user=request.current_user,
                                                                     service=service)
        if not streetview_resource_service:
            abort(404, "No service found")
        return fn(*args, **kwargs)
    return wrapper


def streetview_instance_permissions(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        instance_id = kwargs.get("instance_id")

        streetview_instance = StreetviewService.getInstance(instance_id)
        if not streetview_instance:
            abort(404, "No instance found")
        if request.current_user != streetview_instance.streetview.user:
            abort(403, "Access denied")
        return fn(*args, **kwargs)
    return wrapper


def streetview_sequence_permissions(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        instance_id = kwargs.get("sequence_id")
        sequence = StreetviewService.getSequenceFromId(instance_id)
        # possible that its a int instance_id as both are supported so check that.
        if not sequence:
            sequence = StreetviewService.getSequence(instance_id)

        if not sequence:
            abort(404, "No sequence found")
        if request.current_user != sequence.streetview_instance.streetview.user:
            abort(403, "Access denied")
        return fn(*args, **kwargs)
    return wrapper
