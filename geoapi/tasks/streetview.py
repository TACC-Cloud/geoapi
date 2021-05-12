from geoapi.services.users import UserService
import os
import uuid
from uuid import UUID
from typing import Dict
from pathlib import Path

from geoapi.celery_app import app
from geoapi.exceptions import ApiException
from geoapi.models import User, Streetview
from geoapi.utils.agave import AgaveUtils
from geoapi.utils.streetview import (get_project_streetview_dir,
                                     make_project_streetview_dir,
                                     remove_project_streetview_dir,
                                     MapillaryUtils)
from geoapi.log import logging
import geoapi.services.features as features
from geoapi.services.streetview import StreetviewService
from geoapi.services.notifications import NotificationsService

logger = logging.getLogger(__file__)


def upload(user: User, params: Dict):
    if (params['mapillary']):
        if not user.mapillary_jwt:
            raise ApiException("Not authenticated to mapillary!")

    if (params['google']):
        if not user.google_jwt:
            raise ApiException("Not authenticated to google!")
    if len(NotificationsService.getProgressStatus('in_progress')) > 5:
        # TODO: Find better solution for limiting uploads.
        NotificationsService.create(user, "warning", "Maximum number of uploads in progress!")
        return

    from_tapis_to_streetview.delay(user.id,
                                   params['folder'],
                                   params['google'],
                                   params['mapillary'],
                                   params['retry'])


def delete_upload_session(user: User, task_uuid: UUID):
    NotificationsService.deleteProgress(task_uuid)
    remove_project_streetview_dir(user.id, task_uuid)


def create_upload_session(user: User, task_uuid: UUID):
    NotificationsService.createProgress(user, "error", "test", task_uuid=task_uuid)
    make_project_streetview_dir(user.id, task_uuid)


def _from_tapis(user: User, task_uuid: UUID, systemId: str, path: str):
    client = AgaveUtils(user.jwt)
    listing = client.listing(systemId, path)
    files_in_directory = listing[1:]

    base_filepath = get_project_streetview_dir(user.id, task_uuid)

    # TODO Should handle retry
    if not os.path.isdir(base_filepath):
        make_project_streetview_dir(user.id, task_uuid)
    else:
        remove_project_streetview_dir(user.id, task_uuid)
        make_project_streetview_dir(user.id, task_uuid)
        NotificationsService.create(user,
                                    "success",
                                    "Cleaning up previous session before upload.")

    img_list = []

    done_files = 0
    files_length = len(files_in_directory)

    for item in files_in_directory:
        if item.type == "dir":
            NotificationsService.create(user,
                                        "warning",
                                        "Invalid upload type. Disregarding...")
            continue
        if item.path.suffix.lower().lstrip('.') not in features.FeaturesService.IMAGE_FILE_EXTENSIONS:
            continue
        try:
            img_name = os.path.join(str(base_filepath), Path(item.path).name)
            img_list.append(img_name)
            client.getRawFileToPath(systemId, item.path, img_name)

            done_files += 1

            NotificationsService.updateProgress(task_uuid=task_uuid,
                                                status="in_progress",
                                                message="From Tapis [1/3]",
                                                progress=int(done_files / files_length * 100),
                                                logItem={"uploadFiles": img_list})
        except Exception as e:
            logger.exception("Could not import file from agave: {} :: {}, {}".format(systemId, path, e))
            done_files -= 1
            error_message = "Error importing {f}".format(f=path)
            NotificationsService.updateProgress(task_uuid=task_uuid,
                                                logItem={"errorMessage": error_message})
            NotificationsService.create(user, "error", error_message)
            raise Exception
    if len(img_list) == 0:
        error_message = "No images have been uploaded to geoapi!"
        NotificationsService.updateProgress(task_uuid=task_uuid,
                                            logItem={"errorMessage": error_message})
        raise ValueError("No images have been uploaded to geoapi!")


def _to_mapillary(user: User, task_uuid: UUID):
    token = user.mapillary_jwt

    mapillary_user = MapillaryUtils.get_user(user.mapillary_jwt)

    try:
        NotificationsService.updateProgress(task_uuid,
                                            "in_progress",
                                            "To Mapillary [2/3]", 0)
        MapillaryUtils.authenticate(user.id, token)
        MapillaryUtils.upload(user.id, task_uuid, mapillary_user['username'])
    except Exception as e:
        NotificationsService.updateProgress(task_uuid=task_uuid,
                                            logItem={"errorMessage": e})
        raise e


def _to_google():
    pass


# NOTE: At the time of writing, Mapillary's api does not return the sequence
#       key(s) of the uploaded images. However, they do support searching
#       existing sequences. We need to manually parse the logs to keep
#       track of them in geoapi. mapillary_tools keeps logs in the
#       .mapillary/<IMG_NAMES> directories of the upload root.
#       We are specifically parsing the bounding box coordinates and
#       start/end dates using some utility functions that mapillary_tools provides.
#
#       Relative documentation here: https://www.mapillary.com/developer/api-documentation
def _mapillary_finalize(user: User, streetview: Streetview, task_uuid: UUID):
    list_per_sequence_mapping = MapillaryUtils.get_sequence_mappings(user, task_uuid)
    combined_list_sequence_mappings = MapillaryUtils.get_filtered_sequence_mappings(list_per_sequence_mapping)

    if len(combined_list_sequence_mappings) == 0:
        error_message = "Error during Mapillary finalize. No logs have been found for the uploaded files."
        logger.error(error_message)
        raise Exception(error_message)
    else:
        for seq in combined_list_sequence_mappings:
            StreetviewService.createSequence(streetview_id=streetview.id,
                                             service='mapillary',
                                             start_date=seq['start_date'],
                                             end_date=seq['end_date'],
                                             bbox='{}, {}, {}, {}'.format(seq['lon_min'], seq['lat_min'], seq['lon_max'], seq['lat_max'])
                                             )


def _mapillary_check_error(user: User, streetview: Streetview, task_uuid: UUID):
    # Final error parsing and delete temporary directory
    if MapillaryUtils.upload_error(user, task_uuid) > 0:
        StreetviewService.delete(streetview.id)
        error_message = "Error during Mapillary upload."
        NotificationsService.updateProgress(task_uuid,
                                            "error",
                                            error_message)
        raise Exception(error_message)


def _google_finalize():
    pass


@app.task(rate_limit="5/s")
def from_tapis_to_streetview(userId: int,
                             dir: Dict,
                             google: bool,
                             mapillary: bool,
                             retry: bool):
    user = UserService.get(userId)
    task_uuid = uuid.uuid3(uuid.NAMESPACE_URL, dir['system'] + dir['path'])
    existing_progress = NotificationsService.getProgressUUID(task_uuid)
    current_streetview = StreetviewService.getFromSystemPath(user, dir['system'], dir['path'])

    # Initialize progress notification and streetview object
    if retry:
        NotificationsService.deleteProgress(task_uuid)

    if len(existing_progress) > 0:
        if existing_progress[0].status == 'done' or existing_progress[0].status == 'in_progress':
            NotificationsService.create(user, "warning", "Path {f} is already in progress or uploaded."
                                        .format(f=(dir['system'] + dir['path'])))
            return
        elif existing_progress[0].status == 'error':
            # TODO: Improve this so that it considers incremental upload progress for _from_tapis
            NotificationsService.create(user, "success", "Retrying to upload {f}."
                                        .format(f=(dir['system'] + dir['path'])))
            NotificationsService.deleteProgress(task_uuid)

    if len(current_streetview) > 0:
        NotificationsService.create(user, "warning", "Path {f} is already uploaded."
                                    .format(f=(dir['system'] + dir['path'])))
        return

    NotificationsService.createProgress(user,
                                        "created",
                                        "Preparing upload process...",
                                        task_uuid,
                                        {
                                            "publishInfo": {
                                                "system": dir['system'],
                                                "path": dir['path'],
                                                "mapillary": mapillary,
                                                "google": google
                                            }
                                        })

    streetview = StreetviewService.create(user.id,
                                          dir['system'],
                                          dir['path'])

    # Get from tapis
    try:
        _from_tapis(user, task_uuid, dir['system'], dir['path'])
    except Exception as e:
        logger.error(e)
        StreetviewService.delete(streetview.id)
        NotificationsService.updateProgress(task_uuid,
                                            "error",
                                            str(e))
        NotificationsService.create(user, "error", "Nothing has been uploaded from {f}"
                                    .format(f=dir['path']))
        remove_project_streetview_dir(user.id, task_uuid)
        return

    # Upload to mapillary
    if mapillary:
        try:
            _to_mapillary(user, task_uuid)
        except Exception as e:
            logger.error(e)
            StreetviewService.delete(streetview.id)
            NotificationsService.updateProgress(task_uuid,
                                                "error",
                                                "Mapillary tools failed!")
            NotificationsService.create(user, "error",
                                        "Nothing has been uploaded to Mapillary"
                                        .format(f=dir['path']))
            remove_project_streetview_dir(user.id, task_uuid)
            return

        try:
            _mapillary_finalize(user, streetview, task_uuid)
            _mapillary_check_error(user, streetview, task_uuid)
        except Exception as e:
            logger.error(e)
            StreetviewService.delete(streetview.id)
            NotificationsService.updateProgress(task_uuid,
                                                "error",
                                                "Mapillary had errors during upload!")
            NotificationsService.create(user, "error", "Mapillary had errors during upload!".format(f=dir['path']))
            remove_project_streetview_dir(user.id, task_uuid)
            return

    NotificationsService.updateProgress(task_uuid,
                                        "success",
                                        "Finished Upload")

    remove_project_streetview_dir(user.id, task_uuid)
