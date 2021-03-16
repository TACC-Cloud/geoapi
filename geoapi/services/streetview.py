from os.path import isdir

from requests.models import Response
from geoapi.services.projects import ProjectsService
import os
import time
import pathlib
import uuid
import json
import tempfile
import requests
from typing import List, IO, Dict

from mapillary_tools import api_v3 as mapillary_api
from mapillary_tools import uploader as mapillary_uploader
from mapillary_tools import processing as mapillary_processing

from geoapi.services.images import ImageService, ImageData
from geoapi.services.vectors import VectorService
from geoapi.services.projects import ProjectsService
from geoapi.services.users import UserService
from geoapi.models import Feature, FeatureAsset, Overlay, User, Streetview
from geoapi.db import db_session
from geoapi.exceptions import InvalidGeoJSON, ApiException
from geoapi.utils.assets import make_project_asset_dir, delete_assets, get_asset_relative_path
from geoapi.utils.streetview import get_project_streetview_dir, delete_streetview_dir
from geoapi.log import logging
from geoapi.utils import geometries
from geoapi.utils.agave import AgaveUtils
from geoapi.tasks import streetview

logger = logging.getLogger(__name__)

class StreetviewService:

    ###################
    # Streetview Auth #
    ###################

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

        # print(authorized)
        # print(url)
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
        REDIRECT_URL = 'http://localhost:8000/projects/streetview/' + service + '/callback'

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
    def uploadFilesToMapillary(user: User, projectId: int, data: Dict):
        try:
            streetview.upload_files_from_tapis_to_streetview.delay(user.id,
                                                                   user.tenant_id,
                                                                   projectId,
                                                                   data['folder'],
                                                                   data['google'],
                                                                   data['mapillary'],
                                                                   data['retry'])
        except ApiException as e:
            print(e)

    # @staticmethod
    # def createStreetview(username: str, tenantId: str, systemId: int, path: str, sequenceKey: str, service: str):
    #     """

    #     :rtype: User
    #     """
    #     u = UserService.getUser(username, tenantId)

    #     s = Streetview(systemId=systemId,
    #                    path=path,
    #                    service=service,
    #                    user_id=u.id,
    #                    sequenceKey=sequenceKey)

    #     db_session.add(s)
    #     db_session.commit()
    #     return s

    # @staticmethod
    # def deleteStreetview(streetviewId: int):
    #     """

    #     :rtype: User
    #     """
    #     s = db_session.query(Streetview).get(streetviewId)
    #     delete_streetview_dir(s.userId, s.path, s.uuid)

    #     db_session.delete(s)
    #     db_session.commit()

    ########################
    # Uploading From Tapis #
    ########################

    @staticmethod
    def fromGPanoImageFile(username: str, tenant: str, service: str):
        pass

    # Did this in ImagesService
    @staticmethod
    def is_gpano():
        return False

    #################
    # Mapillary API #
    #################
    # Link this to bottom function
    @staticmethod
    def getMapillaryOrganizationKey():
        pass

    @staticmethod
    def getMapillaryUser(username: str, projectId: int):
        os.environ["MAPILLARY_WEB_CLIENT_ID"] = "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"
        proj = ProjectsService.get(projectId)
        token = StreetviewService.getStreetviewServiceToken(username, proj.tenant_id, 'mapillary')
        return mapillary_api.get_user(token['access_token'])

    @staticmethod
    def getMapillaryUserOrganizations(username: str, projectId):
        os.environ["MAPILLARY_WEB_CLIENT_ID"] = "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"
        proj = ProjectsService.get(projectId)
        token = StreetviewService.getStreetviewServiceToken(username, proj.tenant_id, 'mapillary')
        user = StreetviewService.getMapillaryUser(username, projectId)
        return mapillary_api.fetch_user_organizations(user['key'], token)

    @staticmethod
    def getMapillaryUserSequences(dsUser: User, username: str, tenantId: str, projectId):
        os.environ["MAPILLARY_WEB_CLIENT_ID"] = "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"
        # proj = ProjectsService.get(projectId)
        # token = StreetviewService.getStreetviewServiceToken(dsUser.username, tenantId, 'mapillary')
        token = StreetviewService.getStreetviewServiceToken('ipark', tenantId, 'mapillary')
        # user = StreetviewService.getMapillaryUser(username, projectId)
        user = StreetviewService.getMapillaryUser('ipark', projectId)
        headers = {"Authorization": f"Bearer {token}"}
        os.environ["MAPILLARY_WEB_CLIENT_ID"] = "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"
        resp = requests.get(
            f"https://a.mapillary.com/v3/users/{user['key']}/sequences",
            params={"client_id": "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def getMapillaryImageSequence(userId, system_path: str):
        os.environ["MAPILLARY_WEB_CLIENT_ID"] = "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"
        streetview_path = get_project_streetview_dir(userId, system_path)

        if not os.path.isdir(streetview_path):
            return None

        total_files = mapillary_uploader.get_total_file_list(streetview_path)

        if len(total_files) == 0:
            return None

        log_root = mapillary_uploader.log_rootpath(total_files[0])
        sequence_data_path = os.path.join(log_root, "sequence_process.json")
        if not os.path.isfile(sequence_data_path):
            return None

        sequence_data = mapillary_processing.load_json(sequence_data_path)
        return sequence_data['MAPSequenceUUID']

        # for img in total_files:
        #     log_root = mapillary_uploader.log_rootpath(img)
        #     sequence_data_path = os.path.join(log_root, "sequence_process.json")
        #     if os.path.isfile(sequence_data_path):
        #         sequence_data = mapillary_processing.load_json(sequence_data_path)
        # return sequence_data['MAPSequenceUUID']

    @staticmethod
    def getMapillaryUserKey(mapillary_username: str):
        os.environ["MAPILLARY_WEB_CLIENT_ID"] = "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"
        return mapillary_api.get_user_key(mapillary_username)

    # TODO Later for optimization
    @staticmethod
    def getMapillarySessionData():
        pass

    #########################
    # Google Streetview API #
    #########################
    # https://developers.google.com/streetview/publish/resumable-uploads

    @staticmethod
    def getGoogleSessionData():
        pass

    @staticmethod
    def getGoogleSequenceData():
        pass

    @staticmethod
    def getGoogleUserData():
        pass

    ####################
    # Streetview Model #
    ####################

    @staticmethod
    def get(streetviewId: int) -> Streetview:
        """
        Retreive a single Streetview
        :param streetviewId: int
        :return: Streetview
        """
        return db_session.query(Streetview).get(streetviewId)

    @staticmethod
    def getStreetviewBySystemPath(systemId: str, pathId: str) -> List[Streetview]:
        return db_session.query(Streetview)\
                         .filter(Streetview.systemId == systemId)\
                         .filter(Streetview.path == pathId)\
                         .all()

    @staticmethod
    def delete(streetviewId: int) -> None:
        """
        Delete a Streetview.
        :param streetviewId: int
        :return: None
        """
        sv = db_session.query(Streetview).get(streetviewId)
        db_session.delete(sv)
        db_session.commit()

    @staticmethod
    def getStreetviews(username: str) -> List[Streetview]:
        # FIXME: Put this in User
        user = db_session.query(User)\
                         .filter(User.username == username)\
                         .first()

        streetviews = db_session.query(Streetview).filter_by(user_id=user.id).all()
        return streetviews

    @staticmethod
    def getStreetviewSequences(username: str) -> List[str]:
        sv_list = StreetviewService.getStreetviews(username)
        return list(map(lambda x: x.sequenceKey, sv_list))

    @staticmethod
    def getStreetviewSystemPaths(username: str) -> List[tuple]:
        sv_list = StreetviewService.getStreetviews(username)
        return list(map(lambda x: (x.systemId, x.path), sv_list))

    @staticmethod
    def retrieveMapillaryStreetviewSequence(sequenceKey: str, username: str, tenantId: str) -> Dict:
        # NOTE DS username
        token = StreetviewService.getStreetviewServiceToken(username, tenantId, 'mapillary')
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"https://a.mapillary.com/v3/sequences/{sequenceKey}",
            params={"client_id": "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"},
            headers=headers,
        )

        return resp.json()

    @staticmethod
    def retrieveStreetviewSequences(username: str, service: str, tenantId: str) -> List[Dict]:
        seq_list = StreetviewService.getStreetviewSequences(username)
        system_path_list = StreetviewService.getStreetviewSystemPaths(username)
        my_seqs = []

        for i in range(len(seq_list)):
            if service == 'mapillary':
                # geoseq = StreetviewService.retrieveMapillaryStreetviewSequence(seq_list[i], username, tenantId)
                geoseq = StreetviewService.retrieveMapillaryImages(seq_list[i], username, tenantId)
            else:
                geoseq = {"test": "test"}

            seq_obj = {
                "feature": geoseq,
                "systemPath": system_path_list[i]
            }

            my_seqs.append(seq_obj)

        return my_seqs

    # TODO: Make a wrapper to parse service (also in routes)
    @staticmethod
    def retrieveMapillaryImage(imageKey: str, username: str, tenantId: str) -> Dict:
        # NOTE DS username
        token = StreetviewService.getStreetviewServiceToken(username, tenantId, 'mapillary')
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"https://a.mapillary.com/v3/images/{imageKey}",
            params={"client_id": "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"},
            headers=headers,
        )

        return resp.json()

    @staticmethod
    def retrieveMapillaryImages(sequenceKey: str, username: str, tenantId: str) -> Dict:
        # NOTE DS username
        token = StreetviewService.getStreetviewServiceToken(username, tenantId, 'mapillary')

        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"https://a.mapillary.com/v3/images",
            params={
                "client_id": "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi",
                "per_page": 1000,
                "sequence_keys": [sequenceKey]
            },
            headers=headers,
        )

        return resp.json()

    @staticmethod
    def create(userId: int, systemId: str, pathId: str, sequenceKey: str, mapillary: bool, google: bool) -> None:
        """
        Create a Streetview model to link to tapis path and service.
        :param userId: int
        :param systemId: str
        :param pathId: str
        :param sequenceKey: str
        :param mapillary: bool
        :param google: bool
        :return: None
        """
        sv = Streetview()
        sv.user_id = userId
        sv.path = pathId
        sv.systemId = systemId
        sv.mapillary = google
        sv.google = mapillary
        sv.sequenceKey = sequenceKey
        db_session.add(sv)
        db_session.commit()
