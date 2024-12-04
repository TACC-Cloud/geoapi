import os
import pathlib
import shutil
import re
import json
import subprocess
import datetime
from typing import List
from uuid import UUID

from geoapi.services.notifications import NotificationsService

from geoapi.models import User
from geoapi.exceptions import ApiException
from geoapi.settings import settings
from geoapi.log import logging


logger = logging.getLogger(__file__)


def make_project_streetview_dir(userId: int, task_uuid: UUID) -> str:
    """
    Creates a directory for a temporary streetview paths in the STREETVIEW_DIR location
    :param projectId: int
    :return:
    """
    base_filepath = get_project_streetview_dir(userId, task_uuid)
    pathlib.Path(base_filepath).mkdir(parents=True, exist_ok=True)
    return base_filepath


def get_project_streetview_dir(userId: int, task_uuid: UUID) -> str:
    """
    Get streetview temporary directory
    :param userId: int
    :param task_uuid: UUID
    :return: string: streetview temporary directory
    """
    return os.path.join(settings.STREETVIEW_DIR, str(userId), str(task_uuid))


def is_project_streetview_dir(userId: int, task_uuid: UUID) -> bool:
    return os.path.isdir(get_project_streetview_dir(userId, task_uuid))


def remove_project_streetview_dir(userId: int, task_uuid: UUID):
    """
    Get streetview temporary directory
    :param projectId: int
    :return: string: streetview temporary directory
    """
    shutil.rmtree(get_project_streetview_dir(userId, task_uuid))


def get_streetview_path(*relative_paths) -> str:
    """
    streetview temporary directory with relative paths to get absolute path to streetview path
    :param relative_paths: str
    :return: string: absolute path to streetview dir
    """
    return os.path.join(settings.STREETVIEW_DIR, *relative_paths)


def get_streetview_relative_path(task_uuid: UUID) -> str:
    """
    Get path which is relative to streetview temporary directory

    If path is "/streetivew_dir/1/something.txt", then return
    "1/something.txt"

    :param path: str
    :return: string: relative path
    """
    return os.path.relpath(str(task_uuid), start=settings.STREETVIEW_DIR)


class MapillaryUtils:
    @staticmethod
    def get_auth_file(userId: int):
        return os.path.join(settings.STREETVIEW_DIR, str(userId), "mapillary_auth")

    @staticmethod
    def is_authenticated(userId):
        return os.path.isfile(MapillaryUtils.get_auth_file(userId))

    @staticmethod
    def authenticate(userId: int, jwt: str, service_user: str):
        if MapillaryUtils.is_authenticated(userId):
            return

        command = [
            "/opt/conda/bin/mapillary_tools",
            "authenticate",
            "--user_name",
            service_user,
            "--jwt",
            jwt,
        ]

        try:
            subprocess.run(
                command,
                check=True,
                env={
                    "MAPILLARY_CLIENT_TOKEN": settings.MAPILLARY_CLIENT_TOKEN,
                    "MAPILLARY_CONFIG_PATH": MapillaryUtils.get_auth_file(userId),
                },
            )
        except subprocess.CalledProcessError as e:
            error_message = "Errors occurred during Mapillary authentication for user with userId: {}. {}".format(
                userId, e
            )
            raise ApiException(error_message)

    @staticmethod
    def parse_upload_output():
        pass

    @staticmethod
    def upload(
        database_session,
        userId: int,
        task_uuid: UUID,
        service_user: str,
        organization_key: str,
    ):
        command = [
            "/opt/conda/bin/mapillary_tools",
            "process_and_upload",
            get_project_streetview_dir(userId, task_uuid),
            "--user_name",
            service_user,
            "--organization_key",
            organization_key,
        ]

        try:
            prog = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env={
                    "MAPILLARY_CLIENT_TOKEN": settings.MAPILLARY_CLIENT_ID,
                    "MAPILLARY_CONFIG_PATH": MapillaryUtils.get_auth_file(userId),
                },
                text=True,
            )
            NotificationsService.updateProgress(
                database_session, task_uuid, "created", "Uploading to Mapillary"
            )

            for line in iter(prog.stdout.readline, b""):
                if line == "":
                    break

                catch_upload_status = re.compile(r"(.*): (\d+(?=%))")
                upload_status_match = re.search(catch_upload_status, str(line.rstrip()))
                if upload_status_match:
                    NotificationsService.updateProgress(
                        database_session,
                        task_uuid,
                        "in_progress",
                        upload_status_match.group(1),
                        int(float(upload_status_match.group(2))),
                    )
                else:
                    NotificationsService.updateProgress(
                        database_session, task_uuid, "created", "Processing upload..."
                    )

        except Exception as e:
            error_message = "Error occurred mapillary_tools upload task for user with id: {} \n {}".format(
                userId, str(e)
            )
            logger.error(error_message)
            raise Exception(error_message)
        else:
            logger.info("Subprocess finished")
            return

    @staticmethod
    def extract_uploaded_sequences(user: User, task_uuid: UUID) -> List:
        desc_path = os.path.join(
            get_project_streetview_dir(user.id, task_uuid),
            "mapillary_image_description.json",
        )

        mapped_sequences = {}
        uploaded_sequences = []

        if os.path.isfile(desc_path):
            with open(desc_path, "rb") as jf:
                descs = json.load(jf)
                for desc in descs:
                    seq = desc["MAPSequenceUUID"]
                    lat = desc["MAPLatitude"]
                    lon = desc["MAPLongitude"]
                    time = datetime.datetime.strptime(
                        desc["MAPCaptureTime"], "%Y_%m_%d_%H_%M_%S_%f"
                    )

                    try:
                        mapped_sequences[seq]
                    except KeyError:
                        mapped_sequences[seq] = {}

                    try:
                        mapped_sequences[seq]["lat"]
                    except KeyError:
                        mapped_sequences[seq]["lat"] = []

                    try:
                        mapped_sequences[seq]["lon"]
                    except KeyError:
                        mapped_sequences[seq]["lon"] = []

                    try:
                        mapped_sequences[seq]["time"]
                    except KeyError:
                        mapped_sequences[seq]["time"] = []

                    mapped_sequences[seq]["lat"].append(lat)
                    mapped_sequences[seq]["lon"].append(lon)
                    mapped_sequences[seq]["time"].append(time)

            for key, val in mapped_sequences.items():
                uploaded_sequences.append(
                    {
                        "start_date": min(val["time"]),
                        "end_date": max(val["time"]),
                        "lat_max": max(val["lat"]),
                        "lat_min": min(val["lat"]),
                        "lon_max": max(val["lon"]),
                        "lon_min": min(val["lon"]),
                    }
                )
        return uploaded_sequences
