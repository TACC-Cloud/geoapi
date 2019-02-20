
from functools import wraps
from flask import abort
from flask import request
from flask_restplus import reqparse
import jwt
from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService

parser = reqparse.RequestParser()


def jwt_decoder(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = request.headers.get('x-jwt-assertion')
        try:
            decoded = jwt.decode(token, 'your-256-bit-secret', 'HS256')
            username = decoded["http://wso2.org/claims/subscriber"]
        except:
            abort(400, 'could not decode JWT')

        user = UserService.getUser(username)
        if not user:
            user = UserService.create(username)
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
