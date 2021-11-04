from geoapi.services.users import UserService
import os
import uuid
from uuid import UUID
from typing import Dict
from pathlib import Path

from geoapi.celery_app import app
from geoapi.exceptions import (ApiException,
                               StreetviewAuthException,
                               StreetviewLimitException,
                               StreetviewExistsException)
from geoapi.models import User, Streetview, StreetviewInstance, streetview
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

    service = params['service']
    system_id = params['system_id']
    path = params['path']
    organization_id = params['organization_id']

    streetview_service = StreetviewService.getByService(user, service)

    if (not streetview_service.token or not streetview_service.service_user):
        logger.error('Not authenticated to {} for user: {}'\
            .format(params['service'],
                    user.username))
        raise StreetviewAuthException('Not authenticated to {}!'.format(service))

    # TODO: Find better solution for limiting uploads.
    if len(NotificationsService.getProgressStatus('in_progress')) > 5:
        message = 'Maximum number of uploads in progress!'
        NotificationsService.create(user, 'warning', message)
        raise StreetviewLimitException(message)

    # TODO: Implement retry
    from_tapis_to_streetview.delay(user.id,
                                   streetview_service.id,
                                   system_id,
                                   path,
                                   organization_id)

def progress_error(user: User,
                 task_uuid: UUID,
                 status: str=None,
                 message: str=None,
                 logItem: Dict=None):
  logger.error(message)
  message = 'Error occurred'
  NotificationsService.create(user, status, message)
  NotificationsService.updateProgress(task_uuid=task_uuid,
                                      status=status,
                                      message=message,
                                      logItem=logItem)

def clean_session(streetview_instance: StreetviewInstance,
                  user: User,
                  task_uuid: UUID,
                  status: str=None,
                  message: str=None,
                  logItem: dict=None,
                  remove_dir: bool=False):
    StreetviewService.deleteInstance(streetview_instance.id)
    progress_error(user, task_uuid, status, message, logItem)
    if remove_dir:
        # TODO: Change to include service after user id
        remove_project_streetview_dir(user.id, task_uuid)

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
            done_files -= 1
            raise Exception("Could not import file from agave: {} :: {}, {}" \
                            .format(systemId, path, e))

    if len(img_list) == 0:
        raise Exception("No images have been uploaded to geoapi!")


def _to_mapillary(user: User, streetview_instance: StreetviewInstance, task_uuid: UUID, organization_id: str):
    streetview_service = streetview_instance.streetview
    token = streetview_service.token

    service_user = streetview_service.service_user

    try:
        NotificationsService.updateProgress(task_uuid,
                                            "in_progress",
                                            "To Mapillary [2/3]", 0)

        MapillaryUtils.authenticate(user.id, token, service_user)
        MapillaryUtils.upload(user.id, task_uuid, service_user, organization_id)
    except Exception as e:
        raise Exception("Errors during mapillary upload task {} for user {}: Error: {}" \
                      .format(task_uuid, user.username, e))

# NOTE: At the time of writing, Mapillary's api does not return the sequence
#       key(s) of the uploaded images. However, they do support searching
#       existing sequences. We need to manually parse the logs to keep
#       track of them in geoapi. mapillary_tools keeps logs in the
#       .mapillary/<IMG_NAMES> directories of the upload root.
#       We are specifically parsing the bounding box coordinates and
#       start/end dates using some utility functions that mapillary_tools provides.
#
#       Relative documentation here: https://www.mapillary.com/developer/api-documentation
def _mapillary_finalize(user: User, streetview_instance: StreetviewInstance, task_uuid: UUID):
    list_per_sequence_mapping = MapillaryUtils.get_sequence_mappings(user, task_uuid)
    combined_list_sequence_mappings = MapillaryUtils.get_filtered_sequence_mappings(list_per_sequence_mapping)

    if len(combined_list_sequence_mappings) == 0:
        error_message = "Error during Mapillary finalize. No logs have been found for the uploaded files."
        raise Exception(error_message)
    else:
        for seq in combined_list_sequence_mappings:
            StreetviewService.createSequence(streetview_instance=streetview_instance,
                                             start_date=seq['start_date'],
                                             end_date=seq['end_date'],
                                             bbox='{}, {}, {}, {}'.format(seq['lon_min'], seq['lat_min'], seq['lon_max'], seq['lat_max'])
                                             )


def _mapillary_check_error(user: User,
                           streetview_instance: StreetviewInstance,
                           task_uuid: UUID):
    if MapillaryUtils.upload_error(user, task_uuid) > 0:
        error_message = "Error during Mapillary upload task {} for user {}." \
            .format(task_uuid, user.username)
        raise Exception(error_message)


# TODO: Handle retry (deleteprogress) and different progress statuses and resuming
def check_existing_upload(user, streetview_service, task_uuid, system_id, path):
    existing_progress = NotificationsService.getProgressUUID(task_uuid)
    existing_instance = StreetviewService.getInstanceFromSystemPath(streetview_service.id,
                                                                   system_id,
                                                                   path)
    # TODO: Handle existing progress
    if existing_progress or existing_instance:
        raise StreetviewExistsException("Path {f} is already in progress or uploaded."
                                        .format(f=(system_id + path)))


# TODO: Ensure that just user works and not userid (previously took userid)
@app.task(rate_limit="5/s")
def from_tapis_to_streetview(user_id: int,
                             streetview_service_id: int,
                             system_id: str,
                             path: str,
                             organization_id: str):
    user = UserService.get(user_id);
    streetview_service = StreetviewService.get(streetview_service_id)

    task_uuid = uuid.uuid3(uuid.NAMESPACE_URL, system_id + path)

    try:
        check_existing_upload(user, streetview_service, task_uuid, system_id, path)
    except StreetviewExistsException as e:
        NotificationsService.create(user, 'warning', str(e))
        return


    # Initialize progress notification and streetview object
    NotificationsService.createProgress(user,
                                        "created",
                                        "Preparing upload process...",
                                        task_uuid,
                                        {
                                            "publishInfo": {
                                                "system": system_id,
                                                "path": path,
                                                "service": streetview_service.service
                                            }
                                        })
    streetview_instance = StreetviewService.createInstance(streetview_service.id,
                                                           system_id,
                                                           path)

    # Get from tapis
    try:
      _from_tapis(user, task_uuid, system_id, path)
    # TODO: Handle
    except Exception as e:
        error_message = "Error during getting files from tapis system:{} path:{} \
        for streetview upload task: {} for user: {}. Error Message: {}" \
              .format(system_id, path, task_uuid, user.username, e)
        clean_session(streetview_instance,
                      user,
                      task_uuid,
                      'error',
                      error_message,
                      logItem={'errorMessage': error_message},
                      remove_dir=True)
        return

    if streetview_service.service == 'mapillary':
        try:
            _to_mapillary(user, streetview_instance, task_uuid)
        except Exception as e:
            error_message = "Error during uploading to mapillary for streetview task: {} \
              for user: {}. Error message: {}" \
              .format(task_uuid, user.username, e)
            clean_session(streetview_instance,
                          user,
                          task_uuid,
                          'error',
                          error_message,
                          logItem={'errorMessage': error_message},
                          remove_dir=True)
            return

        try:
            _mapillary_finalize(user, streetview_instance, task_uuid)
            _mapillary_check_error(user, streetview_instance, task_uuid)
        except Exception as e:
            error_message = "Error during finalization of mapillary upload for streetview task: {} \
            for user: {}. Error message: {}" \
                  .format(task_uuid, user.username, e)
            clean_session(streetview_instance,
                          user,
                          task_uuid,
                          'error',
                          error_message,
                          remove_dir=True)
            return

    NotificationsService.updateProgress(task_uuid,
                                        "success",
                                        "Finished Upload")

    remove_project_streetview_dir(user.id, task_uuid)
