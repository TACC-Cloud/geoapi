# from geoapi.utils.streetivew import get_project_streetview_dir
from logging import exception
import os
import concurrent
import shutil
import uuid
from uuid import UUID
from pathlib import Path
from celery import uuid as celery_uuid
import concurrent.futures
import requests
import subprocess
from typing import List, Dict, IO
from geoapi.services.images import ImageService, ImageData, is_gpano

import json

from mapillary_tools import uploader as mapillary_uploader

from geoapi.celery_app import app
from geoapi.exceptions import InvalidCoordinateReferenceSystem, ApiException
from geoapi.models import User, ObservableDataProject, Task
from geoapi.utils.agave import AgaveUtils, get_system_users
from geoapi.utils.streetview import get_project_streetview_dir, make_project_streetview_dir, remove_project_streetview_dir, delete_streetview, get_streetview_relative_path, is_project_streetview_dir, authenticate_mapillary, test_to_mapillary, upload_to_mapillary, get_project_streetview_dir
from geoapi.log import logging
import geoapi.services.features as features
from geoapi.services.imports import ImportsService
from geoapi.services.vectors import SHAPEFILE_FILE_ADDITIONAL_FILES
import geoapi.services.point_cloud as pointcloud
from geoapi.services.streetview import StreetviewService
from geoapi.tasks.lidar import convert_to_potree, check_point_cloud, get_point_cloud_info
from geoapi.db import db_session
from geoapi.services.notifications import NotificationsService
from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService

logger = logging.getLogger(__file__)

# TODO: implement revoke hook
# NOTE: Should delete files created by a task (need systemid/path)
# NOTE: Should remove progress notifications related to task
@app.task(rate_limit="5/s")
def revoke_streetview_upload(w):
    pass


@app.task(rate_limit="5/s")
def upload_files_from_tapis_to_streetview(userId: int, tenantId: str, projectId: int, dir: Dict, google: bool, mapillary: bool, retry: bool):
    task_uuid = uuid.uuid3(uuid.NAMESPACE_URL, dir['system'] + dir['path'])
    temp_progress = NotificationsService.getProgressUUID(task_uuid)
    current_streetview = StreetviewService.getStreetviewBySystemPath(dir['system'], dir['path'])
    user = db_session.query(User).get(userId)

    # TODO: if retry, you should delete the current progress (separate from this)
    # TODO: Check also case where it's done but not notification doesn't exist
    #       (have to check inside the streetview model)

    if len(temp_progress) > 0:
        if temp_progress[0].status == 'done' or temp_progress[0].status == 'in_progress':
            NotificationsService.create(user, "warning", "Path {f} is already in progress or uploaded."
                                        .format(f=(dir['system'] + dir['path'])))
            return
        elif temp_progress[0].status == 'error':
            # TODO: Improve this so that one can follow up previous progress if uploading to geoapi
            NotificationsService.create(user, "success", "Retrying to upload {f}."
                                        .format(f=(dir['system'] + dir['path'])))
            NotificationsService.deleteProgress(task_uuid)

    if len(current_streetview) > 0:
        NotificationsService.create(user, "warning", "Path {f} is already uploaded."
                                    .format(f=(dir['system'] + dir['path'])))
        return

    NotificationsService.createProgress(userId, tenantId, "created", "", task_uuid, {
        "publishInfo": {
            "system": dir['system'],
            "path": dir['path'],
            "mapillary": mapillary,
            "google": google
        }
    })

    # Import
    # TODO: Maybe add condition to check if file exists?
    # TODO: Also check if there is a path with the same progress (racey maybe lock before going into it)
    # TODO IF retry, then remove it
    # TODO There are more cases than just "retry",
    #      - basic condition is that retry should happen iff task is finished as error
    #      - [x] if not (in_progress or done), it should just not attempt in the first place
    #      - [x] if error, the files should be preserved (i.e. not deleted on geoapi)
    #      - [x] if done, the files are deleted and either the done task is there or there is a streetview model
    #      - [x] Only allow retry when the previous UUID session failed and pressed the retry button
    #      - [] in the case of retry, ther are couple possibility
    #        - [] one is when failed from the uploading to tapis step
    #          - NOTE in this case compare all files? honestly not sure what to do here
    #          - Maybe have a list that keeps track of all the currently uploaded files
    #        - [x] in the other case (error when uploading to mapillary), continue from the current files
    #          - solved by not removing it from the first place on error
    #        - [] This all assumes that the files in tapis haven't changed during deciding to upload and
    #      - [] xif error and the user decides to just retry from scratch (another option) then just do that

    if (not retry):
        try:
            import_temporary_file_from_agave(userId, projectId, task_uuid, dir['system'], dir['path'])
        except Exception as e:
            print("No images were uploaded")
            NotificationsService.updateProgress(task_uuid,
                                                "error",
                                                str(e))
            NotificationsService.create(user, "error", "Nothing has been uploaded from {f}".format(f=dir['path']))

    # TODO: 1. Make import work properly
    #       2. Make upload work (maybe spawn in different task/process)
    #         - This might have to handle model creation
    #       3. Maybe spawn processes on file loop
    #         1. IF sessions allow asynchronous addition
    #           - Make each process do the whole workflow (import/upload/delete)
    #         2. IF sessions do not allow asynchronous addition
    #           - Make each process handle imports separately (from tapis)
    #           - Block
    #           - After each import is done, handle exports separately [loop through tmp dir]
    #           - Block
    #           - After each export is done delete files
    #         3. IF not much benefit from async (i.e. no need for prompt imports)
    #           - Just do everything synchronously
    #       4. Delete temporary files (iff can't use file-objects for this)
    # try:
    #     import_temporary_file_from_agave(userId, systemdId, path, projectId)

    try:
        upload_files_to_mapillary(userId, task_uuid, projectId, dir['path'])
    except Exception as e:
        NotificationsService.updateProgress(task_uuid,
                                            "error",
                                            "Mapillary tools failed!")
        raise ApiException("Mapillary tools failed!")

    sequence_key = StreetviewService.getMapillaryImageSequence(userId, dir['path'])

    # NOTE: This assumes that there is a sequence path (which is removed)
    # NOTE: This should never fail..
    if sequence_key == None:
        NotificationsService.updateProgress(task_uuid,
                                            "error",
                                            "Mapillary sequence")
        raise ValueError("No sequence provided, cannot proceed with upload")

    print(sequence_key)

    # FIXME: should remove userId because given user? check out
    # TODO: wrap try catch
    StreetviewService.create(userId,
                             dir['system'],
                             dir['path'],
                             sequence_key,
                             mapillary,
                             google)

    # NOTE: Assume that photos were uploaded (otherwise might need to keep for resume)
    # NOTE: Maybe there should be a hashed lock file (maybe not reconsider)
    # TODO: ensure that the "failed_file_list" is empty
    if (len(mapillary_uploader.get_failed_upload_file_list(get_project_streetview_dir(userId, dir['path']))) > 0):
        NotificationsService.updateProgress(task_uuid,
                                            "error",
                                            "There are files that failed to upload")
        raise ApiException("There are files that failed to upload!")
    else:
        # TODO Client should send confirm and button option to remove task notification from notification list
        NotificationsService.updateProgress(task_uuid,
                                            "success",
                                            "Finished Upload")

        remove_project_streetview_dir(userId, dir['path'])


def import_temporary_file_from_agave(userId: int, projectId: int, task_uuid: UUID, systemId: str, path: str):
    user = db_session.query(User).get(userId)
    client = AgaveUtils(user.jwt)
    listing = client.listing(systemId, path)
    files_in_directory = listing[1:]
    filenames_in_directory = [str(f.path) for f in files_in_directory]

    base_filepath = get_project_streetview_dir(userId, path)

    # FIXME This part should handle retry (when upload to geoapi fails)
    if (not os.path.isdir(base_filepath)):
        make_project_streetview_dir(userId, path)
    else:
        NotificationsService.create(user, "success", "Cleaning up previous session before upload.")
        remove_project_streetview_dir(userId, path)
        make_project_streetview_dir(userId, path)

    img_list = []
    error_list = []

    # FIXME
    done_files = 0
    files_length = len(files_in_directory)

    for item in files_in_directory:
        if item.type == "dir":
            NotificationsService.create(user, "warning", "This upload contains non-gpano images. Disregarding...")
            continue
        if item.path.suffix.lower().lstrip('.') not in features.FeaturesService.IMAGE_FILE_EXTENSIONS:
            continue
        try:
            # item_system_path = os.path.join(item.system, str(item.path).lstrip("/"))
            # targetFile = ImportsService.getImport(projectId, systemId, str(item.path))
            # +Check if already uploaded the directory path+
            # TODO Check if it is in DB
            # if item_system_path:
            #     logger.info("Already imported {}".format(item_system_path))
            #     continue
            # listing = client.listing(systemId, item.path)[0]
            # meta = client.getMetaAssociated(listing.uuid)
            # for key, value in meta.items():
            #     logger.info("Awesome!!!!!! \n\n\n\n\n\n {}".format(key))
            #     logger.info("Awesome!!!!!! \n\n\n\n\n\n {}".format(value))

            # tmpFile = client.getFile(systemId, item.path)
            # # rawFile = client.getRawFile(systemId, item.path)
            # # tmpFile.filename = Path(path).name

            # TODO Handle this later
            # if (not is_gpano(tmpFile)):
            #     tmpFile.close()
            #     error_message = "This upload contains non-gpano images. Disregarding..."
            #     error_list.append(error_message)
            #     # NotificationsService.updateProgress(task_uuid=task_uuid,
            #     #                                     extraDataItem={"errorMessages": error_list})
            #     NotificationsService.create(user, "warning", error_message)
            #     continue

            asset_uuid = uuid.uuid4()

            print("Writing to..")
            img_name = os.path.join(str(base_filepath), str(asset_uuid) + '.jpg')
            img_list.append(img_name)
            print(img_name)

            # Write manually
            client.getRawFileToPath(systemId, item.path, img_name)

            done_files += 1

            print("here this")
            NotificationsService.updateProgress(task_uuid=task_uuid,
                                                status="in_progress",
                                                message="From Tapis [1/3]",
                                                progress=int(done_files / files_length * 100),
                                                extraDataItem={"uploadFiles": img_list})
        except Exception as e:
            # db_session.rollback()
            logger.exception("Could not import file from agave: {} :: {}".format(systemId, path))
            done_files -= 1
            # NotificationsService.updateProgress("in_progress_tapis_error", str(e), task_uuid, int(done_files / files_length * 100))
            error_message = "Error importing {f}".format(f=path)
            error_list.append(error_message)
            # NotificationsService.updateProgress(task_uuid, "error", "From tapis", 0, extraDataItem={"errorMessages": error_list})

            # TODO Not user given?
            NotificationsService.create(user, "error", error_message)
    if len(img_list) == 0:
        # NotificationsService.updateProgress("no files uploded", "", task_uuid, int(done_files / files_length * 100))
        # NotificationsService.updateProgress("error", "No images have been uploaded! [from tapis to geoapi]", task_uuid, int(done_files / files_length * 100))
        raise ValueError("No images have been uploaded to geoapi!")
    else:
        # NotificationsService.updateProgress(task_uuid,
        #                                     "success",
        #                                     "Finished upload to geoapi")
        print("Uploads to geoapi successful!")


# # TODO: Should get link
def upload_files_to_mapillary(userId: int, task_uuid: UUID, projectId: int, path: str):
    # TODO Check for authentication status (if token expired, request for refresh)
    proj = ProjectsService.get(projectId)
    user = db_session.query(User).get(userId)

    token = StreetviewService.getStreetviewServiceToken(user.username, proj.tenant_id, 'mapillary')
    access_token = token['access_token']

    # print(access_token)
    # print(proj.id)
    # print(user.username)
    # Handle stdout to get progress

    mapillary_user = StreetviewService.getMapillaryUser(user.username, projectId)

    try:
        NotificationsService.updateProgress(task_uuid, "in_progress", "To Mapillary [2/3]", 0)
        authenticate_mapillary(userId, access_token)
        upload_to_mapillary(userId, path, task_uuid, mapillary_user['username'])
        print("upload to mapillary successful!")
    except Exception as e:
        # FIXME: Proper handling (send user notification)
        raise ApiException(str(e))

    # test_to_mapillary(userId, path, task_uuid, user.username)
