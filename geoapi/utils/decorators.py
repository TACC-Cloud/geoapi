
from functools import wraps
from flask import abort
from flask import request
import jwt
from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService
from geoapi.services.features import FeaturesService
from geoapi.services.point_cloud import PointCloudService
from geoapi.settings import settings
from geoapi.utils import jwt_utils
from geoapi.log import logger
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import base64


def get_pub_key():
    pkey = base64.b64decode(settings.JWT_PUB_KEY)
    pub_key = serialization.load_der_public_key(pkey,
                                                backend=default_backend())
    return pub_key


def jwt_decoder(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        pub_key = get_pub_key()
        # TODO: validate token
        jwt_header_name, token, tenant = jwt_utils.jwt_tenant(request.headers)
        try:
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


def project_permissions(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        projectId = kwargs.get("projectId")
        proj = ProjectsService.get(projectId)
        if not proj:
            abort(404, "No project found")
        current_user = request.current_user
        access = UserService.canAccess(current_user, projectId)
        if not access:
            abort(403, "Access denied")
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
