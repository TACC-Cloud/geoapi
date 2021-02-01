from geoapi.services.projects import ProjectsService
import os
import time
import pathlib
import uuid
import json
import tempfile
from typing import List, IO, Dict

from geoapi.services.images import ImageService, ImageData
from geoapi.services.vectors import VectorService
from geoapi.services.projects import ProjectsService
from geoapi.services.users import UserService
from geoapi.models import Feature, FeatureAsset, Overlay, User
from geoapi.db import db_session
from geoapi.exceptions import InvalidGeoJSON, ApiException
from geoapi.utils.assets import make_project_asset_dir, delete_assets, get_asset_relative_path
from geoapi.log import logging
from geoapi.utils import geometries
from geoapi.utils.agave import AgaveUtils

logger = logging.getLogger(__name__)

class StreetviewService:
    @staticmethod
    def streetviewRequest(username: str, projectId: int, service: str):
        SERVER_STATE = {
            'username': username,
            'projectId': projectId
        }

        my_state = json.dumps(SERVER_STATE, separators=(',', ':'))

        url = None
        proj = ProjectsService.get(projectId)

        token = StreetviewService.getStreetviewServiceToken(username, proj.tenant_id, service)
        authorized = False

        if token == None or token == {}:
            url = StreetviewService.getStreetviewURL(service, my_state)
        else:
            authorized = True
            if service == 'google' and token['expiration_date'] < time.time():
                # token = None
                authorized = False
                url = StreetviewService.getStreetviewURL(service, my_state)

        streetview_token = {
            # "token": json.dumps(token),
            "authorized": authorized,
            "url": url
        }

        return streetview_token

    @staticmethod
    def getStreetviewURL(service: str, state: str):
        GOOGLE_CLIENT_ID = '573001329633-1p0k8rko13s6n2p2cugp3timji3ip9f0.apps.googleusercontent.com'
        MAPILLARY_CLIENT_ID = 'VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi'
        GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
        MAPILLARY_AUTH_URL = 'https://www.mapillary.com/connect'
        GOOGLE_SCOPE = 'https://www.googleapis.com/auth/streetviewpublish'
        MAPILLARY_SCOPE = 'user:email+user:read+user:write+public:write+public:upload+private:read+private:write+private:upload'
        REDIRECT_URL = 'http://localhost:8000/users/streetview/' + service + '/callback'

        if service == 'google':
            return GOOGLE_AUTH_URL + "?" + "&client_id=" + GOOGLE_CLIENT_ID \
                + "&scope=" + GOOGLE_SCOPE  + "&redirect_uri=" + REDIRECT_URL \
                + "&response_type=code" + "&state=" + state
        else:
            return MAPILLARY_AUTH_URL + "?" + "&client_id=" + MAPILLARY_CLIENT_ID \
                + "&scope=" + MAPILLARY_SCOPE  + "&redirect_uri=" + REDIRECT_URL \
                + "&response_type=token" + "&state=" + state

    @staticmethod
    def getStreetviewServiceToken(username: str, tenant: str, service: str):
        user = db_session.query(User)\
                         .filter(User.username == username)\
                         .filter(User.tenant_id == tenant)\
                         .first()
        if service == 'google':
            return user.google_jwt
        else:
            return user.mapillary_jwt

    @staticmethod
    def setStreetviewServiceToken(username: str, tenant: str, service: str, token: Dict) -> None:
        user = UserService.getUser(username, tenant)
        # NOTE: Assume user exists
        if service == 'google':
            user.google_jwt = token
        else:
            user.mapillary_jwt = token
        db_session.commit()

    @staticmethod
    def deleteStreetviewServiceToken(username: str, tenant: str, service: str):
        user = UserService.getUser(username, tenant)
        if service == 'google':
            user.google_jwt = None
        else:
            user.mapillary_jwt = None
        db_session.commit()

    @staticmethod
    def uploadFromTapisToService(username: str, tenant: str, service: str):
        user = UserService.getUser(username, tenant)
        if service == 'google':
            user.google_jwt = None
        else:
            user.mapillary_jwt = None
        db_session.commit()
