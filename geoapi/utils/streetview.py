import os
import pathlib
import glob
import shutil
import uuid
import re
import sys
import json
import requests
import subprocess
import datetime
from typing import Dict, List
from uuid import UUID

from mapillary_tools import api_v3 as mapillary_api
from mapillary_tools import uploader as mapillary_uploader
from mapillary_tools import processing as mapillary_processing

from geoapi.services.streetview import StreetviewService
from geoapi.services.notifications import NotificationsService

from geoapi.models import User
from geoapi.settings import settings

from geoapi.settings import settings
from geoapi.log import logging


logger = logging.getLogger(__file__)


def make_project_streetview_dir(userId: int, path: str) -> str:
    """
    Creates a directory for a temporary streetview paths in the STREETVIEW_DIR location
    :param projectId: int
    :return:
    """
    base_filepath =  get_project_streetview_dir(userId, path)
    pathlib.Path(base_filepath).mkdir(parents=True, exist_ok=True)
    return base_filepath


def get_project_streetview_dir(userId: int, path: str) -> str:
    """
    Get streetview temporary directory
    :param projectId: int
    :return: string: streetview temporary directory
    """
    pathId = uuid.uuid3(uuid.NAMESPACE_URL, path)
    return os.path.join(settings.STREETVIEW_DIR, str(userId), str(pathId))


def is_project_streetview_dir(userId: int, path: str) -> bool:
    return os.path.isdir(get_project_streetview_dir(userId, path))


def remove_project_streetview_dir(userId: int, path: str):
    """
    Get streetview temporary directory
    :param projectId: int
    :return: string: streetview temporary directory
    """
    shutil.rmtree(get_project_streetview_dir(userId, path))


def get_streetview_path(*relative_paths) -> str:
    """
    streetview temporary directory with relative paths to get absolute path to streetview path
    :param relative_paths: str
    :return: string: absolute path to streetview dir
    """
    return os.path.join(settings.STREETVIEW_DIR, *relative_paths)


def get_streetview_relative_path(path: str) -> str:
    """
    Get path which is relative to streetview temporary directory

    If path is "/streetivew_dir/1/something.txt", then return
    "1/something.txt"

    :param path: str
    :return: string: relative path
    """
    return os.path.relpath(path, start=settings.STREETVIEW_DIR)


def delete_streetview(userId: int, path: str, uuid: str):
    """
    Delete streetview related to a single feature

    :param projectId: int
    :param uuid: str
    :return:
    """
    for streetview_file in glob.glob('{}/*{}*'.format(get_project_streetview_dir(userId, path), uuid)):
        if os.path.isfile(streetview_file):
            os.remove(streetview_file)
        else:
            shutil.rmtree(streetview_file)


def delete_streetview_dir(userId: int, path: str, uuid: str):
    """
    Delete streetview related to a single feature

    :param projectId: int
    :param uuid: str
    :return:
    """
    for streetview_file in glob.glob('{}/*{}*'.format(get_project_streetview_dir(userId, path), uuid)):
        if os.path.isfile(streetview_file):
            os.remove(streetview_file)
        else:
            shutil.rmtree(streetview_file)


class MapillaryUtils:
    @staticmethod
    def get_auth_file(userId: int):
        return os.path.join(settings.STREETVIEW_DIR, str(userId), "mapillary_auth")


    @staticmethod
    def is_authenticated(userId):
        return os.path.isfile(MapillaryUtils.get_auth_file(userId))


    @staticmethod
    def authenticate(userId: int, jwt: str):
        if MapillaryUtils.is_authenticated(userId):
            return

        command = [
            '/usr/local/bin/mapillary_tools',
            '--advanced',
            'authenticate',
            '--config_file',
            MapillaryUtils.get_auth_file(userId),
            '--jwt',
            jwt
        ]

        subprocess.run(command,
                       capture_output=True,
                       env={'MAPILLARY_WEB_CLIENT_ID': settings.MAPILLARY_CLIENT_ID})


    @staticmethod
    def upload(userId: int, path: str, task_uuid: UUID, mapillary_username: str):
        command = [
            '/usr/local/bin/mapillary_tools',
            'process_and_upload',
            '--import_path',
            get_project_streetview_dir(userId, path),
            '--user_name',
            mapillary_username
        ]

        try:
            prog = subprocess.Popen(command,
                                    stdout=subprocess.PIPE,
                                    stdin=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    env={
                                        'MAPILLARY_WEB_CLIENT_ID': settings.MAPILLARY_CLIENT_ID,
                                        'GLOBAL_CONFIG_FILEPATH': MapillaryUtils.get_auth_file(userId)
                                    },
                                    text=True)
            NotificationsService.updateProgress(task_uuid, "in_progress", "To Mapillary [2/3]", 50)

            for line in iter(prog.stdout.readline, b''):
                if line == '':
                    break
                catch_upload_percent = re.compile(r'\d+\.\d+(?=%|$)')
                catch_upload_logs = re.compile(r'images left')
                upload_percent_match = re.findall(catch_upload_percent, str(line.rstrip()))
                upload_logs_match = re.findall(catch_upload_logs, str(line.rstrip()))
                if len(upload_percent_match) > 0 and len(upload_logs_match) > 0:
                    NotificationsService.updateProgress(task_uuid, "in_progress", "To Mapillary [2/2]", int(float(upload_percent_match[0])))
                else:
                    NotificationsService.updateProgress(task_uuid, "created", "Processing images...")

                catch_retry = re.compile(r'Retry uploading previously failed image uploads')
                retry_match = re.findall(catch_retry, str(line.rstrip()))
                if len(retry_match) > 0:
                    prog.communicate(input='n\n')[0]
                    raise Exception

                catch_error = re.compile(r'Error')
                error_match = re.findall(catch_error, str(line.rstrip()))
                if len(error_match) > 0:
                    raise Exception

        except (OSError, subprocess.CalledProcessError) as exception:
            logging.info('Exception occured: ' + str(exception))
            logging.info('Subprocess failed')
            return False
        except Exception:
            raise Exception
        else:
            logging.info('Subprocess finished')
            return True


    @staticmethod
    def get_user(jwt: str):
        return mapillary_api.get_user(jwt)


    @staticmethod
    def get_image_sequence(userId, system_path: str):
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


    @staticmethod
    def get_image_capture_time(userId, system_path: str):
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
        return sequence_data['MAPCaptureTime']


    @staticmethod
    def get_user_key(mapillary_username: str):
        return mapillary_api.get_user_key(mapillary_username)


    # TODO Later for optimization
    @staticmethod
    def get_session_data():
        pass


    @staticmethod
    def upload_error(user: User, path: str):
        return len(mapillary_uploader.
                   get_failed_upload_file_list(get_project_streetview_dir(user.id, path)))


    @staticmethod
    def get_sequence_mappings(user: User, path: str):
        upload_file_list = mapillary_uploader.get_success_upload_file_list(get_project_streetview_dir(user.id, path),
                                                                   False)
        params = {}
        list_per_sequence_mapping = {}
        for image in upload_file_list:
            log_root = mapillary_uploader.log_rootpath(image)
            upload_params_path = os.path.join(
                log_root, "upload_params_process.json"
            )
            if os.path.isfile(upload_params_path):
                with open(upload_params_path, "rb") as jf:
                    params[image] = json.load(jf)
                    sequence = params[image]["key"]
                    if sequence in list_per_sequence_mapping:
                        list_per_sequence_mapping[sequence].append(image)
                    else:
                        list_per_sequence_mapping[sequence] = [image]
        return list_per_sequence_mapping


    @staticmethod
    def get_filtered_sequence_mappings(mappings: Dict) -> List:
        combined_list_sequence_mappings = []
        for key, val in mappings.items():
            dates = []
            lons = []
            lats = []
            for img in val:
                log_root = mapillary_uploader.log_rootpath(img)
                params_path = os.path.join(
                    log_root, "geotag_process.json"
                )
                if os.path.isfile(params_path):
                    with open(params_path, "rb") as jf:
                        my_params = json.load(jf)
                        dates.append(datetime.datetime.strptime(my_params['MAPCaptureTime'], "%Y_%m_%d_%H_%M_%S_%f"))
                        lons.append(my_params['MAPLongitude'])
                        lats.append(my_params['MAPLatitude'])
            seq_obj = {
                'start_date': min(dates),
                'end_date': max(dates),
                'lat_max': max(lats),
                'lat_min': min(lats),
                'lon_max': max(lons),
                'lon_min': min(lons)
            }
            combined_list_sequence_mappings.append(seq_obj)
        return combined_list_sequence_mappings

    @staticmethod
    def search_sequence(user: User, params: Dict) -> Dict:
        req_params = {"client_id": settings.MAPILLARY_CLIENT_ID}
        req_params.update(params)
        headers = {"Authorization": f"Bearer {user.mapillary_jwt}"}

        resp = requests.get(
            f"https://a.mapillary.com/v3/sequences",
            params=req_params,
            headers=headers,
        )

        return resp.json()
