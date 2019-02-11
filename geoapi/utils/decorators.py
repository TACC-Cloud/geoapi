
from functools import wraps
from flask import abort
from flask import request
from flask_restplus import reqparse
import jwt
from geoapi.dao.users import UserDAO

parser = reqparse.RequestParser()


def jwt_decoder(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = request.headers.get('x-jwt-assertion')
        print(token)
        try:
            decoded = jwt.decode(token, 'your-256-bit-secret', 'HS256')
            print(decoded)
            username = decoded["http://wso2.org/claims/subscriber"]
        except:
            abort(400, 'could not decode JWT')

        user = UserDAO.getUser(username)
        if not user:
            user = UserDAO.create(username)
        
        return fn(*args, **kwargs)
    return wrapper


def project_permissions(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):

        print('Checking permissions')
        print(kwargs)
        return fn(*args, **kwargs)
    return wrapper
