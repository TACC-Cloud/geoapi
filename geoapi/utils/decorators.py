
from functools import wraps
from flask import abort
from flask import request
from flask_restplus import reqparse
import jwt
from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService
from geoapi.services.features import FeaturesService
from geoapi.settings import settings
from geoapi.utils import jwt_utils

parser = reqparse.RequestParser()

def jwt_decoder(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # token = request.headers.get('x-jwt-assertion')
        jwt_header_name, token, tenant = jwt_utils.jwt_tenant(request.headers)
        try:
            decoded = jwt.decode(token, settings.JWT_SECRET_KEY, 'HS256')
            username = decoded["http://wso2.org/claims/subscriber"]
        except:
            abort(400, 'could not decode JWT')

        user = UserService.getUser(username, tenant)
        if not user:
            user = UserService.create(username, token, tenant)
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
        return fn(*args, **kwargs)

    return wrapper