from geoapi.models.feature import Feature, FeatureAsset
from geoapi.services.users import UserService
import os
import uuid
from uuid import UUID
from typing import Dict
from pathlib import Path
import requests
import json
import celery
from celery import uuid as celery_uuid

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, LineString

from geoapi.celery_app import app
from geoapi.exceptions import (StreetviewAuthException,
                               StreetviewLimitException,
                               StreetviewExistsException)
from geoapi.models import User, StreetviewInstance, StreetviewSequence, Task
from geoapi.utils.agave import AgaveUtils
from geoapi.utils.streetview import (get_project_streetview_dir,
                                     make_project_streetview_dir,
                                     remove_project_streetview_dir,
                                     MapillaryUtils)
from geoapi.log import logging
from geoapi.utils import features as features_util
from geoapi.services.streetview import StreetviewService
from geoapi.services.notifications import NotificationsService
from geoapi.db import create_task_session

logger = logging.getLogger(__file__)


def publish(database_session, user: User, params: Dict):
    service = params['service']
    system_id = params['system_id']
    path = params['path']
    organization_key = params['organization_key']

    streetview_service = StreetviewService.getByService(database_session, user, service)

    if not streetview_service.token or not streetview_service.service_user:
        logger.exception('Not authenticated to {} for user:{}'.format(params['service'], user.username))
        raise StreetviewAuthException('Not authenticated to {}!'.format(service))

    # TODO: Find better solution for limiting uploads.
    if len(NotificationsService.getProgressStatus(database_session, 'in_progress')) > 5:
        message = 'Maximum number of uploads in progress!'
        NotificationsService.create(database_session, user, 'warning', message)
        raise StreetviewLimitException(message)

    # TODO: Implement retry
    from_tapis_to_streetview.delay(user.id,
                                   streetview_service.id,
                                   system_id,
                                   path,
                                   organization_key)


def progress_error(database_session,
                   user: User,
                   task_uuid: UUID,
                   status: str = None,
                   message: str = None,
                   logItem: Dict = None):
    logger.error(message)
    message = 'Error occurred'
    NotificationsService.create(database_session, user, status, message)
    NotificationsService.updateProgress(database_session, task_uuid=task_uuid,
                                        status=status,
                                        message=message,
                                        logItem=logItem)


def clean_session(database_session,
                  streetview_instance: StreetviewInstance,
                  user: User,
                  task_uuid: UUID,
                  status: str = None,
                  message: str = None,
                  logItem: dict = None):
    StreetviewService.deleteInstance(database_session, streetview_instance.id)
    progress_error(database_session, user, task_uuid, status, message, logItem)
    remove_project_streetview_dir(user.id, task_uuid)


def _from_tapis(database_session, user: User, task_uuid: UUID, systemId: str, path: str):
    """
    Get files from tapis and place in a temporary streetview directory
    :param user: User
    :param task_uuid: UUID
    :param systemId: str
    :param path: str
    """
    client = AgaveUtils(database_session, user)
    listing = client.listing(systemId, path)
    files_in_directory = listing[1:]

    base_filepath = get_project_streetview_dir(user.id, task_uuid)

    if os.path.isdir(base_filepath):
        remove_project_streetview_dir(user.id, task_uuid)
        logger.info("Cleaning up previous session before upload.")
    make_project_streetview_dir(user.id, task_uuid)

    img_list = []

    done_files = 0
    files_length = len(files_in_directory)

    # TODO https://jira.tacc.utexas.edu/browse/WG-94 get multiple files at the same time
    for item in files_in_directory:
        if item.type == "dir":
            continue
        if item.path.suffix.lower().lstrip('.') not in features_util.IMAGE_FILE_EXTENSIONS:
            continue
        try:
            img_name = os.path.join(str(base_filepath), Path(item.path).name)
            img_list.append(img_name)
            client.get_file_to_path(systemId, item.path, img_name)

            done_files += 1

            NotificationsService.updateProgress(database_session,
                                                task_uuid=task_uuid,
                                                status="in_progress",
                                                message="Collecting files from DesignSafe",
                                                progress=int(done_files / files_length * 100),
                                                logItem={"uploadFiles": img_list})

        except Exception as e:
            done_files -= 1
            error_message = "Could not import file from agave: {} :: {}, {}" \
                .format(systemId, path, e)
            logger.exception(error_message)
            raise Exception(error_message)

    if len(img_list) == 0:
        raise Exception("No images have been uploaded to geoapi!")


def _to_mapillary(database_session, user: User, streetview_instance: StreetviewInstance, task_uuid: UUID, organization_key: str):
    streetview_service = streetview_instance.streetview
    token = streetview_service.token

    service_user = streetview_service.service_user

    try:
        NotificationsService.updateProgress(database_session,
                                            task_uuid,
                                            "created",
                                            "Uploading to Mapillary")

        MapillaryUtils.authenticate(user.id, token, service_user)
        MapillaryUtils.upload(user.id, task_uuid, service_user, organization_key)
    except Exception as e:
        msg = "Errors during mapillary upload task {} for user {}: Error: {}".format(task_uuid, user.username, e)
        raise Exception(msg)


# NOTE: At the time of writing, Mapillary's api does not return the sequence
#       key(s) of the uploaded images. However, they do support searching
#       existing sequences. We need to manually parse the logs to keep
#       track of them in geoapi. mapillary_tools keeps logs in the
#       .mapillary/<IMG_NAMES> directories of the upload root.
#       We are specifically parsing the bounding box coordinates and
#       start/end dates using some utility functions that mapillary_tools provides.
#
#       Relative documentation here: https://www.mapillary.com/developer/api-documentation
def _mapillary_finalize(database_session, user: User, streetview_instance: StreetviewInstance, task_uuid: UUID, organization_key: str):
    uploaded_sequences = MapillaryUtils.extract_uploaded_sequences(user, task_uuid)

    if len(uploaded_sequences) == 0:
        error_message = "Error during Mapillary finalize. No logs have been found for the uploaded files."
        raise Exception(error_message)
    else:
        for seq in uploaded_sequences:
            StreetviewService.createSequence(database_session=database_session,
                                             streetview_instance=streetview_instance,
                                             start_date=seq['start_date'],
                                             end_date=seq['end_date'],
                                             bbox='{}, {}, {}, {}'.format(seq['lon_min'], seq['lat_min'], seq['lon_max'], seq['lat_max']),
                                             organization_id=organization_key
                                             )


# TODO: Handle retry (deleteprogress) and different progress statuses and resuming
def check_existing_upload(session, user, streetview_service, task_uuid, system_id, path):
    existing_progress = NotificationsService.getProgressUUID(session, task_uuid)
    existing_instance = StreetviewService.getInstanceFromSystemPath(session,
                                                                    streetview_service.id,
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
                             organization_key: str):
    with create_task_session() as session:

        user = UserService.get(session, user_id)
        streetview_service = StreetviewService.get(session, streetview_service_id)

        task_uuid = uuid.uuid3(uuid.NAMESPACE_URL, system_id + path)

        try:
            check_existing_upload(session, user, streetview_service, task_uuid, system_id, path)
        except StreetviewExistsException as e:
            logger.exception(f"Error checking existing upload for user:{user.username} "
                             f"system_id:{system_id}, path:{path}, {e})")
            NotificationsService.create(session, user, 'warning', str(e))
            return

        # Initialize progress notification and streetview object
        NotificationsService.createProgress(session,
                                            user,
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
        streetview_instance = StreetviewService.createInstance(session,
                                                               streetview_service.id,
                                                               system_id,
                                                               path)

        # Get from tapis
        try:
            _from_tapis(session, user, task_uuid, system_id, path)
        # TODO: Handle
        except Exception as e:
            error_message = "Error during getting files from tapis system:{} path:{} \
            for streetview upload task: {} for user:{}. Error Message: {}" \
                  .format(system_id, path, task_uuid, user.username, e)
            logger.exception(error_message)
            clean_session(session,
                          streetview_instance,
                          user,
                          task_uuid,
                          'error',
                          error_message,
                          logItem={'errorMessage': error_message})
            return

        if streetview_service.service == 'mapillary':
            try:
                _to_mapillary(session, user, streetview_instance, task_uuid, organization_key)
            except Exception as e:
                error_message = "Error during uploading to mapillary for streetview task:{} \
                  for user:{}. Error message: {}" \
                  .format(task_uuid, user.username, e)
                logger.exception(error_message)
                clean_session(session,
                              streetview_instance,
                              user,
                              task_uuid,
                              'error',
                              error_message,
                              logItem={'errorMessage': error_message})
                return

            try:
                _mapillary_finalize(session, user, streetview_instance, task_uuid, organization_key)
            except Exception as e:
                error_message = ("Error during finalization of mapillary upload for streetview task:{} "
                                 "for user:{}. Error message: {}").format(task_uuid, user.username, e)
                logger.exception(error_message)
                clean_session(session,
                              streetview_instance,
                              user,
                              task_uuid,
                              'error',
                              error_message)
                return

        NotificationsService.updateProgress(session,
                                            task_uuid,
                                            "success",
                                            "Finished Upload")

        remove_project_streetview_dir(user.id, task_uuid)


def process_streetview_sequences(database_session, projectId, sequenceId, token) -> Task:
    """
    Process streetview files

    :param projectId: int
    :param sequenceId: int
    :param token: str
    :return: processingTask: Task
    """
    streetview_sequence = database_session.query(StreetviewSequence).get(sequenceId)

    celery_task_id = celery_uuid()
    task = Task()
    task.process_id = celery_task_id
    task.status = "RUNNING"
    task.description = "Processing streetview sequence #{}".format(sequenceId)

    streetview_sequence.task = task

    database_session.add(task)
    database_session.commit()

    logger.info("Starting streetview sequence processing task for sequence (#{}).".format(sequenceId))

    convert_streetview_sequence_to_feature.apply_async(args=[projectId, sequenceId, token], task_id=celery_task_id)

    return task


class StreetviewSequenceProcessingTask(celery.Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.info("Task ({}, streetview sequence {}) failed: {}".format(task_id, args, exc))
        with create_task_session() as session:
            failed_task = session.query(Task).filter(Task.process_id == task_id).first()
            failed_task.status = "FAILED"
            failed_task.description = ""
            session.add(failed_task)
            session.commit()


@app.task(bind=True, base=StreetviewSequenceProcessingTask)
def convert_streetview_sequence_to_feature(self, projectId, sequenceId, token):
    """
    Process point cloud files

    :param projectId: int
    :param seuqenceId: int
    :param token: str
    """
    with create_task_session() as session:

        feature = Feature()
        streetview_sequence = session.query(StreetviewSequence).get(sequenceId)

        sequence_id = streetview_sequence.sequence_id
        original_dir = streetview_sequence.streetview_instance.path
        display_path = original_dir + '/' + sequence_id

        mapillary_api_url = 'https://graph.mapillary.com'

        api_call_headers = {
            'Authorization': 'OAuth ' + token
        }

        sequence_response = requests.get(f"{mapillary_api_url}/image_ids?sequence_id={sequence_id}", headers=api_call_headers)

        jsonResp = json.loads(sequence_response.content).get('data')

        point_features = []

        image_url = ''
        image_id = 0

        if len(jsonResp) != 0:
            image_id = str(jsonResp[0]['id'])
            image_response = requests.get(f"{mapillary_api_url}/{image_id}?fields=thumb_1024_url", headers=api_call_headers)
            image_url = json.loads(image_response.content).get('thumb_1024_url')

        for img in jsonResp:
            image_response = requests.get(f"{mapillary_api_url}/{img['id']}?fields=computed_geometry", headers=api_call_headers)
            image_coordinates = json.loads(image_response.content) \
                .get('computed_geometry') \
                .get('coordinates')
            point_features.append(Point(image_coordinates))

        asset_uuid = uuid.uuid4()

        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="streetview",
            path=image_url,
            display_path=display_path,
            original_path=original_dir,
            original_name=image_id,
            feature=feature
        )

        feature.assets.append(fa)
        streetview_sequence.feature = feature
        streetview_sequence.feature_id = feature.id
        feature.project_id = projectId

        feature.the_geom = from_shape(LineString(point_features), srid=4326)

        streetview_sequence.task.status = "FINISHED"
        streetview_sequence.task.description = ""

        logger.info("Finished streetview sequence processing task for sequence (#{}).".format(sequenceId))

        session.add(feature)
        session.commit()
