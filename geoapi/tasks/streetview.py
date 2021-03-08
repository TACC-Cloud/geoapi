# from geoapi.utils.streetivew import get_project_streetview_dir
from logging import exception
import os
import concurrent
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
from geoapi.utils.streetview import get_project_streetview_dir, make_project_streetview_dir, remove_project_streetview_dir, delete_streetview, get_streetview_relative_path, is_project_streetview_dir, authenticate_mapillary, upload_to_mapillary, get_project_streetview_dir
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

@app.task(rate_limit="5/s")
def upload_files_from_tapis_to_streetview(userId: int, tenantId: str, projectId: int, dir: Dict, google: bool, mapillary: bool, retry: bool):
    task_uuid = uuid.uuid3(uuid.NAMESPACE_URL, dir['system'] + dir['path'])
    NotificationsService.createProgress(userId, tenantId, "created", "", task_uuid)

    # Import
    # TODO: Maybe add condition to check if file exists?
    if (not retry):
        try:
            import_temporary_file_from_agave(userId, projectId, task_uuid, dir['system'], dir['path'])
        except Exception as e:
            print("No images were uploaded")

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
    #     # NOTE This should create folder and files under /tmp
    #     import_temporary_file_from_agave(userId, systemdId, path, projectId)

    #     # TODO: Fill this out
    #     streetview_model = {
    #         tapis_id: systemdId,
    #         tapis_path: path
    #     }

    #     # NOTE: This should have access to files created under /tmp
    #     # NOTE: This should create model link
        # if (google):
        #     streetview_model['streetview_id'] = upload_files_to_google_streetview()
        # if (mapillary):
            # streetview_model['streetview_id'] = upload_files_to_mapillary()
    # if (is_project_streetview_dir(userId, dir['path'])):
    # os.environ["MAPILLARY_WEB_CLIENT_ID"] = "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"
    # upload_files_to_mapillary(userId, task_uuid, projectId, dir['path'])

        # TODO To test this upload has to actually work
        # coolups = StreetviewService.getMapillaryImageSequence(userId, dir['path'])

        # for i in coolups.items():
        #     print(i, coolups[i])

    #     else:
    #         streetview_model['streetview_id'] = upload_files_to_mapillary()

    #     NOTE: Assume that photos were uploaded (otherwise might need to keep for resume)
    #     NOTE: Maybe there should be a hashed lock file (maybe not reconsider)
    #     TODO: ensure that the "failed_file_list" is empty


    # if (len(mapillary_uploader.get_failed_upload_file_list(get_project_streetview_dir(userId, dir['path']))) > 0):
    #     NotificationsService.updateProgress("in_progress_mapillary_failed",
    #                                         "There are files that failed to upload",
    #                                         task_uuid,
    #                                         0)
    #     raise ApiException("There are files that failed to upload!")
    # else:
    #     # TODO Client should send confirm and button option to remove task notification from notification list
    #     NotificationsService.updateProgress("in_progress_mapillary_success",
    #                                         "Successfully uploaded!",
    #                                         task_uuid,
    #                                         0)
        # remove_project_streetview_dir(userId, dir['path'])


def import_temporary_file_from_agave(userId: int, projectId: int, task_uuid: UUID, systemId: str, path: str):
    user = db_session.query(User).get(userId)
    client = AgaveUtils(user.jwt)
    listing = client.listing(systemId, path)
    files_in_directory = listing[1:]
    filenames_in_directory = [str(f.path) for f in files_in_directory]

    base_filepath = get_project_streetview_dir(userId, path)

    if (not os.path.isdir(base_filepath)):
        make_project_streetview_dir(userId, path)

    im_list = []

    # FIXME
    done_files = 0
    files_length = len(files_in_directory)

    for item in files_in_directory:
        if item.type == "dir":
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

            # TODO: 1. Parse XML for GPano
            #         - Check if there is a PIL feature?
            #         - Should send error when image is not supported due to lack of gpano
            #         - Do this for checking now
            #       2. Parse Coordinates
            #       [don't save yet (because lacking proper link back)]
            tmpFile = client.getFile(systemId, item.path)
            tmpFile.filename = Path(path).name

            if (not is_gpano(tmpFile)):
                tmpFile.close()
                continue

            asset_uuid = uuid.uuid4()
            im_list.append(asset_uuid)

            # Write manually
            with open(os.path.join(str(base_filepath), str(asset_uuid) + '.jpeg'), 'wb+') as img:
                img.write(tmpFile.read())
            tmpFile.close()
            img.close()

            done_files += 1
            NotificationsService.updateProgress("in_progress_tapis", "", task_uuid, int(done_files / files_length * 100))
        except Exception as e:
            # db_session.rollback()
            logger.exception("Could not import file from agave: {} :: {}".format(systemId, path))
            done_files -= 1
            NotificationsService.updateProgress("in_progress_tapis_error", str(e), task_uuid, int(done_files / files_length * 100))
            NotificationsService.create(user, "error", "Error importing {f}".format(f=path))
    if len(im_list) == 0:
        raise ValueError("No images have been uploaded")
    else:
        print("Uploads Successful!")


# # TODO: Should get link
def upload_files_to_mapillary(userId: int, task_uuid: UUID, projectId: int, path: str):
    # TODO Check for authentication status (if token expired, request for refresh)
    proj = ProjectsService.get(projectId)
    user = UserService.getUserById(userId)

    token = StreetviewService.getStreetviewServiceToken(user.username, proj.tenant_id, 'mapillary')
    access_token = token['access_token']
    # print(access_token)
    # print(proj.id)
    # print(user.username)
    # Handle stdout to get progress
    user = StreetviewService.getMapillaryUser(user.username, projectId)
    authenticate_mapillary(userId, access_token)
    upload_to_mapillary(userId, path, task_uuid, user['username'])
