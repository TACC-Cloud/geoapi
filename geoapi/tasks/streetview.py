from geoapi.services.users import UserService
import os
import uuid
import shutil
from uuid import UUID
from typing import Dict

from geoapi.celery_app import app
from geoapi.exceptions import ApiException
from geoapi.models import User, Streetview
from geoapi.utils.agave import AgaveUtils
from geoapi.utils.streetview import (get_project_streetview_dir,
                                     make_project_streetview_dir,
                                     remove_project_streetview_dir,
                                     get_project_streetview_dir,
                                     MapillaryUtils)
from geoapi.log import logging
import geoapi.services.features as features
from geoapi.services.streetview import StreetviewService
from geoapi.services.notifications import NotificationsService
from geoapi.services.images import ImageService

logger = logging.getLogger(__file__)


def upload(user: User, request):
    if (request.json['mapillary']):
        if not user.mapillary_jwt:
            raise ApiException("Not authenticated to mapillary!")

    if (request.json['google']):
        if not user.google_jwt:
            raise ApiException("Not authenticated to google!")

    from_tapis_to_streetview.delay(user.id,
                                   request.json['folder'],
                                   request.json['google'],
                                   request.json['mapillary'],
                                   request.json['retry'])


def _from_tapis(user: User, task_uuid: UUID, systemId: str, path: str, retry):
    client = AgaveUtils(user.jwt)
    listing = client.listing(systemId, path)
    files_in_directory = listing[1:]

    base_filepath = get_project_streetview_dir(user.id, path)

    # TODO Should handle retry
    if not os.path.isdir(base_filepath):
        make_project_streetview_dir(user.id, path)
    else:
        remove_project_streetview_dir(user.id, path)
        make_project_streetview_dir(user.id, path)
        NotificationsService.create(user, "success", "Cleaning up previous session before upload.")

    img_list = []
    error_list = []

    done_files = 0
    files_length = len(files_in_directory)

    for item in files_in_directory:
        if item.type == "dir":
            NotificationsService.create(user, "warning", "This upload contains non-gpano images. Disregarding...")
            continue
        if item.path.suffix.lower().lstrip('.') not in features.FeaturesService.IMAGE_FILE_EXTENSIONS:
            continue
        try:
            asset_uuid = uuid.uuid4()

            img_name = os.path.join(str(base_filepath), str(asset_uuid) + '.jpg')
            img_list.append(img_name)

            client.getRawFileToPath(systemId, item.path, img_name)

            done_files += 1

            NotificationsService.updateProgress(task_uuid=task_uuid,
                                                status="in_progress",
                                                message="From Tapis [1/3]",
                                                progress=int(done_files / files_length * 100),
                                                # logItem={"uploadFiles": img_name}
                                                )
                                                # logItem={"uploadFiles": img_list})
        except:
            logger.exception("Could not import file from agave: {} :: {}".format(systemId, path))
            done_files -= 1
            error_message = "Error importing {f}".format(f=path)
            error_list.append(error_message)
            NotificationsService.create(user, "error", error_message)
    if len(img_list) == 0:
        raise ValueError("No images have been uploaded to geoapi!")


def _to_mapillary(user: User, task_uuid: UUID, path: str):
    token = user.mapillary_jwt

    mapillary_user = MapillaryUtils.get_user(user.mapillary_jwt)

    try:
        NotificationsService.updateProgress(task_uuid, "in_progress", "To Mapillary [2/3]", 0)
        MapillaryUtils.authenticate(user.id, token)
        MapillaryUtils.upload(user.id, path, task_uuid, mapillary_user['username'])
    except Exception as e:
        raise ApiException(str(e))


def _to_google():
    pass


def _mapillary_finalize(user: User, streetview: Streetview, task_uuid: UUID, path: str):
    list_per_sequence_mapping = MapillaryUtils.get_sequence_mappings(user, path)
    combined_list_sequence_mappings = MapillaryUtils.get_filtered_sequence_mappings(list_per_sequence_mapping)
    if len(combined_list_sequence_mappings) == 0:
        raise Exception("No parameters")
    else:
        mapillary_user = MapillaryUtils.get_user(user.mapillary_jwt)
        for seq in combined_list_sequence_mappings:
            seq_obj = StreetviewService.createSequence(streetview_id=streetview.id,
                                                       service='mapillary',
                                                       start_date=seq['start_date'],
                                                       end_date=seq['end_date'],
                                                       bbox='{}, {}, {}, {}'.format(seq['lon_min'], seq['lat_min'], seq['lon_max'], seq['lat_max'])
                                                       )


            res = MapillaryUtils.search_sequence(user, {
                'start_date': seq['start_date'],
                'end_date': seq['end_date'],
                'userkeys': mapillary_user['key'],
                'bbox': '{}, {}, {}, {}'.format(seq['lon_min'], seq['lat_min'], seq['lon_max'], seq['lat_max'])
            })
            if len(res['features']) > 0:
                for res_seq in res['features']:
                    StreetviewService.deleteBySequenceKey(res_seq['properties']['key'], streetview.id)

    # Final error parsing and delete temporary directory
    if MapillaryUtils.upload_error(user, path) > 0:
        StreetviewService.delete(streetview.id)
        NotificationsService.updateProgress(task_uuid,
                                            "error",
                                            "There are files that failed to upload")
        raise ValueError("Error in mapillary upload")


def _google_finalize():
    pass


@app.task(rate_limit="5/s")
def from_tapis_to_streetview(userId: int, dir: Dict, google: bool, mapillary: bool, retry: bool):
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

    NotificationsService.createProgress(user, "created", "Preparing upload process...", task_uuid, {
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
    if (not retry):
        try:
            _from_tapis(user, task_uuid, dir['system'], dir['path'], retry)
        except Exception as e:
            logger.error(e)
            StreetviewService.delete(streetview.id)
            NotificationsService.updateProgress(task_uuid,
                                                "error",
                                                str(e))
            NotificationsService.create(user, "error", "Nothing has been uploaded from {f}".format(f=dir['path']))
            return

    # Upload to mapillary
    if mapillary:
        try:
            _to_mapillary(user, task_uuid, dir['path'])
        except Exception as e:
            logger.error(e)
            StreetviewService.delete(streetview.id)
            NotificationsService.updateProgress(task_uuid,
                                                "error",
                                                "Mapillary tools failed!")
            NotificationsService.create(user, "error", "Nothing has been uploaded to Mapillary".format(f=dir['path']))
            return

        try:
            _mapillary_finalize(user, streetview, task_uuid, dir['path'])
        except Exception as e:
            logger.error(e)
            StreetviewService.delete(streetview.id)
            NotificationsService.updateProgress(task_uuid,
                                                "error",
                                                "Mapillary had errors during upload!")
            NotificationsService.create(user, "error", "Mapillary had errors during upload!".format(f=dir['path']))
            return


    NotificationsService.updateProgress(task_uuid,
                                        "success",
                                        "Finished Upload")

    remove_project_streetview_dir(user.id, dir['path'])
