from geoapi.services.notifications import NotificationsService
import os
import sys
import pathlib
import glob
import configparser
import shutil
import asyncio
import uuid
from uuid import UUID
import re
import subprocess
from geoapi.settings import settings

from mapillary_tools import insert_MAPJson as mapillary_insert_MAPJson
from mapillary_tools import process_geotag_properties as mapillary_process_geotag_properties
from mapillary_tools import process_import_meta_properties as mapillary_process_import_meta_properties
from mapillary_tools import process_sequence_properties as mapillary_process_sequence_properties
from mapillary_tools import process_upload_params as mapillary_process_upload_params
from mapillary_tools import process_user_properties as mapillary_process_user_properties

from mapillary_tools import upload as mapillary_upload
from mapillary_tools import post_process as mapillary_post_process
from mapillary_tools import edit_config as mapillary_edit_config
from geoapi.utils.capture_output import CaptureOutput

def make_project_streetview_dir(userId: int, path: str) -> str:
    """
    Creates a directory for a temporary streetview paths in the STREETVIEW_DIR location
    :param projectId: int
    :return:
    """
    dir
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

def get_mapillary_auth_file(userId: int):
    return os.path.join(settings.STREETVIEW_DIR, str(userId), "mapillary_auth")

# def make_mapillary_auth_dir(userId) -> str:
#     base_filepath =  get_mapillary_auth_dir(userId)
#     pathlib.Path(base_filepath).mkdir(parents=True, exist_ok=True)
#     return base_filepath

def mapillary_is_authenticated(userId):
    return os.path.isfile(get_mapillary_auth_file(userId))

# TODO: Capture error cases and other stdout
#       Upload Errors
#       upload.py
#       1. stdin retry (o) "Retry uploading previously failed image uploads? [y/n]: "
#       2. path not exist (this should be handled before) (x)
#       3. "All images have already been uploaded" (o)
#       4. images to upload.,'Please check if all images contain the required Mapillary metadata.
#          If not, you can use "mapillary_tools process" to add them' (this should be handled before) (x)
#       5. f"Uploading {len(upload_file_list)} images with valid mapillary tags
#          (Skipping {len(total_file_list) - len(upload_file_list)})" (not error)
#       6. print(f"Done uploading {len(file_list)} images.")  # improve upload summary (not error)
#       uploader.py
#       7. "Done uploading {len(file_list)} images."
#       8. Authenticate user (this is done when you have the config file) (x)
#       9. http errors (request, timeout, os) [should refresh progress_bar each time [maybe not because it is still same thread/attempt]] (o)
#         - Should look into carefully (get failed)
#      10. keyboard interrupts (shouldn't be an issue)
#       Process Errors
#       processing.py
#       1. Organization key /also uploader.py
#       2. validate organization key also uploader.py
#       3. Organization privacy (also in uploader)
#       4.
#

def filter_mapillary_upload_progress(sout: str, task_uuid: UUID):
    p = re.compile(r'\d+(?=%|$)')
    match = re.findall(p, sout)
    if len(match) > 0:
        NotificationsService.updateProgress("in_progress_mapillary", "", task_uuid, int(match[0]))


async def run_mapillary(cmd, uuid=None):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if stdout:
        print(f'[stdout]\n{stdout.decode()}')
    if stderr:
        print(f'[stderr]\n{stderr.decode()}')

    if uuid and stdout:
        p = re.compile(r'\d+(?=%|$)')
        match = re.findall(p, stdout.decode())
        if len(match) > 0:
            NotificationsService.updateProgress("in_progress_mapillary", "", uuid, int(match[0]))

# def filter_mapillary_upload_progress(sout: str, task_uuid: UUID):
#     p = re.compile(r'\d+(?=%|$)')
#     match = re.findall(p, sout)
#     if len(match) > 0:
#         NotificationsService.updateProgress("in_progress_mapillary", "", task_uuid, int(match[0]))


def authenticate_mapillary(userId: int, jwt: int):
    # if mapillary_is_authenticated(userId):
    #     return

    # os.environ["GLOBAL_CONFIG_FILEPATH"] = get_mapillary_auth_file(userId)
    # os.environ["MAPILLARY_WEB_CLIENT_ID"]
    # os.environ["MAPILLARY_WEB_CLIENT_ID"] = "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"
    # mapillary_edit_config.edit_config(config_file=get_mapillary_auth_file(userId), jwt=jwt)
    # print(os.environ.get("GLOBAL_CONFIG_FILEPATH"))
    # print(os.environ.get("MAPILLARY_WEB_CLIENT_ID"))
    asyncio.run(run_mapillary("{} {} {} {} {} {} {} {}".format(
        "MAPILLARY_WEB_CLIENT_ID=VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi",
        "mapillary_tools",
        "--advanced",
        "authenticate",
        "--config_file",
        get_mapillary_auth_file(userId),
        "--jwt",
        jwt
    )))


    # command = [
    #     # TODO: Get this from settings
    #     "MAPILLARY_WEB_CLIENT_ID=VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"
    #     "mapillary_tools",
    #     "--advanced",
    #     "authenticate",
    #     "--config_file",
    #     get_mapillary_auth_file(userId),
    #     "--jwt",
    #     jwt
    # ]

    # subprocess.run(command, capture_output=True)

# def mapillary_process_upload(userId: int,
#                              path: str,
#                              mapillary_username: str,
#                              skip_subfolders: bool,
#                              duplicate: str,
#                              organization_name: str,
#                              organization_key: str,
#                              private: bool
#                              ):
#     pass

def upload_to_mapillary(userId: int, path: str, task_uuid: UUID, username: str):
    # os.environ["MAPILLARY_WEB_CLIENT_ID"] = "VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"
    # os.environ["GLOBAL_CONFIG_FILEPATH"] = get_mapillary_auth_file(userId)

    # mapillary_process_user_properties(import_path=get_project_streetview_dir(userId, path))
    # mapillary_process_import_meta_properties(import_path=get_project_streetview_dir(userId, path))
    # mapillary_process_geotag_properties(import_path=get_project_streetview_dir(userId, path))
    # mapillary_process_sequence_properties(import_path=get_project_streetview_dir(userId, path))
    # mapillary_process_upload_params(import_path=get_project_streetview_dir(userId, path))
    # mapillary_insert_MAPJson(import_path=get_project_streetview_dir(userId, path))

    # print("Process done.")

    asyncio.run(run_mapillary("{} {} {} {} {} {} {} {}".format(
        "MAPILLARY_WEB_CLIENT_ID=VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi",
        "GLOBAL_CONFIG_FILEPATH=" + get_mapillary_auth_file(userId),
        "mapillary_tools",
        "process_and_upload",
        "--import_path",
        get_project_streetview_dir(userId, path),
        "--user_name",
        username
    ), task_uuid))

    # sys.stdout = CaptureOutput(lambda s: filter_mapillary_upload_progress(s, task_uuid))
    # mapillary_upload(import_path=get_project_streetview_dir(userId, path))

    # command = [
    #     # TODO: Get this from settings
    #     "MAPILLARY_WEB_CLIENT_ID=VDRaeGFzMEtzRnJrMFZwdVYzckd6cjo0ZWY3ZDEzZGIyMWJkZjNi"
    #     "GLOBAL_CONFIG_FILEPATH=" + get_mapillary_auth_file(userId),
    #     "mapillary_tools",
    #     "upload",
    #     "--import_path",
    #     get_project_streetview_dir(userId, path),
    # ]
    # process = subprocess.Popen(command, stdout=subprocess.PIPE)
    # return process

    # sys.stdout = sys.__stdout__
    # mapillary_post_process(import_path=get_project_streetview_dir(userId, path))
