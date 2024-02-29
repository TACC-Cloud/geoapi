import os
import concurrent
from pathlib import Path
import concurrent.futures
from enum import Enum
import time
import datetime
from celery import uuid as celery_uuid
import json

from geoapi.celery_app import app
from geoapi.exceptions import InvalidCoordinateReferenceSystem, MissingServiceAccount, GetUsersForProjectNotSupported
from geoapi.models import User, ProjectUser, ObservableDataProject, Task
from geoapi.utils.agave import (AgaveUtils, SystemUser, get_system_users, get_metadata_using_service_account,
                                AgaveFileGetError, AgaveListingError)
from geoapi.utils import features as features_util
from geoapi.log import logger
from geoapi.services.features import FeaturesService
from geoapi.services.imports import ImportsService
from geoapi.services.vectors import SHAPEFILE_FILE_ADDITIONAL_FILES
import geoapi.services.point_cloud as pointcloud
from geoapi.tasks.lidar import convert_to_potree, check_point_cloud, get_point_cloud_info
from geoapi.db import create_task_session
from geoapi.services.notifications import NotificationsService
from geoapi.services.users import UserService
from geoapi.utils.additional_file import AdditionalFile
from geoapi.utils.geo_location import parse_rapid_geolocation, get_geolocation_from_file_metadata


class ImportState(Enum):
    SUCCESS = 1
    FAILURE = 2
    RETRYABLE_FAILURE = 3


def get_file(client, system_id, path, required):
    """
    Get file callable function to be used for asynchronous future task
    """
    result_file = None
    error = None
    try:
        result_file = client.getFile(system_id, path)
    except Exception as e:  # noqa: E722
        error = e
    return system_id, path, required, result_file, error


def get_additional_files(current_file, system_id: str, path: str, client, available_files=None):
    """
    Get any additional files needed for processing the current file being imported

    Note `available_files` is optional. if provided, then it can be used to fail early if it is known
    that a required file is missing

    :param str current_file: active file that is being imported
    :param str system_id: system of active file
    :param path: path of active file
    :param client:
    :param available_files: list of files that exist (optional)
    :return: list of additional files
    """
    additional_files_to_get = []

    current_file_path = Path(path)
    file_suffix = current_file_path.suffix.lower().lstrip('.')
    if file_suffix == "shp":
        logger.info(f"Determining which shapefile-related files need to be downloaded for file {current_file.filename}")
        for extension, required in SHAPEFILE_FILE_ADDITIONAL_FILES.items():
            additional_file_path = current_file_path.with_suffix(extension)
            if available_files and str(additional_file_path) not in available_files:
                if required:
                    logger.error(f"Could not import required shapefile-related file: agave: {system_id}/{additional_file_path}")
                    raise Exception(f"Required file ({system_id}/{additional_file_path}) missing")
                else:
                    continue
            additional_files_to_get.append(AdditionalFile(path=additional_file_path, required=required))
    elif file_suffix == "rq":
        logger.info(f"Parsing rq file {current_file.filename} to see what assets need to be downloaded ")
        data = json.load(current_file)
        for section in data["sections"]:
            for question in section["questions"]:
                for asset in question.get("assets", []):
                    # determine full path for this asset and add to list
                    additional_file_path = current_file_path.with_name(asset["filename"])
                    additional_files_to_get.append(AdditionalFile(path=additional_file_path, required=True))
        logger.info(f"{len(additional_files_to_get)} assets were found for rq file {current_file.filename}")

        # Seek back to start of file
        current_file.seek(0)
    else:
        # No additional files needed for this file type
        return None

    # Try to get all additional files.
    additional_files_result = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        getting_files_futures = [executor.submit(get_file, client, system_id, additional_file.path, additional_file.required)
                                 for additional_file in additional_files_to_get]
        for future in concurrent.futures.as_completed(getting_files_futures):
            _, additional_file_path, required, result_file, error = future.result()
            if not result_file and required:
                logger.error(f"Could not import a required {file_suffix}-related file: "
                             f"agave: {system_id} :: {additional_file_path}   ---- error: {error}")
                raise Exception(f"Required file ({system_id}/{additional_file_path}) missing")
            if not result_file:
                logger.error(f"Unable to get non-required {file_suffix}-related file: "
                             f"agave: {system_id} :: {additional_file_path}   ---- error: {error}")

                continue
            logger.debug(f"Finished getting {file_suffix}-related file: ({system_id}/{additional_file_path}")
            result_file.filename = Path(additional_file_path).name
            additional_files_result.append(result_file)
    return additional_files_result


@app.task(rate_limit="10/s")
def import_file_from_agave(userId: int, systemId: str, path: str, projectId: int):
    """
    Import file from TAPIS system

    Tapis metdata is checked for location information. If no Tapis metadata, then geolocation information is
    expected to be embedded in the imported file.
    """
    with create_task_session() as session:
        try:
            user = session.query(User).get(userId)
            client = AgaveUtils(user)
            temp_file = client.getFile(systemId, path)
            temp_file.filename = Path(path).name
            additional_files = get_additional_files(temp_file, systemId, path, client)

            optional_location_from_metadata = get_geolocation_from_file_metadata(user, system_id=systemId, path=path)

            FeaturesService.fromFileObj(session, projectId, temp_file, {},
                                        original_path=path, additional_files=additional_files,
                                        location=optional_location_from_metadata)
            NotificationsService.create(session, user, "success", "Imported {f}".format(f=path))
            temp_file.close()
        except Exception as e:  # noqa: E722
            logger.exception("Could not import file from agave: {} :: {}".format(systemId, path))
            NotificationsService.create(session, user, "error", "Error importing {f}".format(f=path))
            raise e


def _update_point_cloud_task(database_session, pointCloudId: int, description: str = None, status: str = None):
    task = pointcloud.PointCloudService.get(database_session, pointCloudId).task
    if description is not None:
        task.description = description
    if status is not None:
        task.status = status
    database_session.add(task)
    database_session.commit()


@app.task(rate_limit="1/s")
def import_point_clouds_from_agave(userId: int, files, pointCloudId: int):
    with create_task_session() as session:
        user = session.query(User).get(userId)
        client = AgaveUtils(user)

        point_cloud = pointcloud.PointCloudService.get(session, pointCloudId)
        celery_task_id = celery_uuid()

        logger.info(f"point cloud:{pointCloudId} conversion started for user:{user.username} and files:{files}")

        # this initial geoapi.model.Task setup should probably be moved out of the celery task and performed
        # in the request processing (i.e. in ProjectPointCloudsFileImportResource) so that a task can be returned in the
        # request. See https://jira.tacc.utexas.edu/browse/WG-85
        task = Task()
        task.process_id = celery_task_id
        task.status = "RUNNING"

        point_cloud.task = task
        session.add(point_cloud)
        session.add(task)
        session.commit()

        new_asset_files = []
        failed_message = None
        for file in files:
            _update_point_cloud_task(session,
                                     pointCloudId,
                                     description="Importing file ({}/{})".format(len(new_asset_files) + 1, len(files)))

            NotificationsService.create(session, user, "success", task.description)

            system_id = file["system"]
            path = file["path"]

            try:
                tmp_file = client.getFile(system_id, path)
                tmp_file.filename = Path(path).name
                file_path = pointcloud.PointCloudService.putPointCloudInOriginalsFileDir(point_cloud.path,
                                                                                         tmp_file,
                                                                                         tmp_file.filename)
                tmp_file.close()

                # save file path as we might need to delete it if there is a problem
                new_asset_files.append(file_path)

                # check if file is okay
                check_point_cloud(file_path)

            except InvalidCoordinateReferenceSystem:
                logger.error(f"Could not import point cloud file ( point cloud: {pointCloudId} , "
                             f"for user:{user.username} due to missing coordinate reference system: {system_id}:{path}")
                failed_message = "Error importing {}: missing coordinate reference system".format(path)
            except Exception as e:
                logger.error(f"Could not import point cloud file for user:{user.username} point cloud: {pointCloudId}"
                             f"from tapis: {system_id}/{path} : {e}")
                failed_message = "Unknown error importing {}:{}".format(system_id, path)

            if failed_message:
                for file_path in new_asset_files:
                    logger.info("removing {}".format(file_path))
                    os.remove(file_path)
                _update_point_cloud_task(session, pointCloudId, description=failed_message, status="FAILED")
                NotificationsService.create(session, user, "error", failed_message)
                return

        _update_point_cloud_task(session, pointCloudId, description="Running potree converter", status="RUNNING")

        point_cloud.files_info = get_point_cloud_info(session, pointCloudId)

        session.add(point_cloud)
        session.commit()

        NotificationsService.create(session,
                                    user,
                                    "success",
                                    "Running potree converter (for point cloud {}).".format(pointCloudId))

    try:
        # use potree converter to convert las to web-friendly format
        # this operation is memory-intensive and time-consuming.
        convert_to_potree(pointCloudId)
        with create_task_session() as session:
            user = session.query(User).get(userId)
            logger.info(f"point cloud:{pointCloudId} conversion completed for user:{user.username} and files:{files}")
            NotificationsService.create(session,
                                        user,
                                        "success",
                                        "Completed potree converter (for point cloud {}).".format(pointCloudId))
    except:  # noqa: E722
        with create_task_session() as session:
            user = session.query(User).get(userId)
            logger.exception(f"point cloud:{pointCloudId} conversion failed for user:{user.username} and files:{files}")
            _update_point_cloud_task(session, pointCloudId, description="", status="FAILED")
            NotificationsService.create(session, user, "error", "Processing failed for point cloud ({})!".format(pointCloudId))


@app.task(rate_limit="5/s")
def import_from_agave(tenant_id: str, userId: int, systemId: str, path: str, projectId: int):
    """
    Recursively import files from a system/path.
    """
    with create_task_session() as session:
        import_from_files_from_path(session, tenant_id, userId, systemId, path, projectId)


def import_from_files_from_path(session, tenant_id: str, userId: int, systemId: str, path: str, projectId: int):
    """
    Recursively import files from a system/path.

    If file has already been imported (i.e. during a previous call), we don't re-import it. Likewise,
    if we have previously failed at importing a file, we do not retry to import the file (unless it was an error like
    file-access where it makes sense to retry at a later time).

    Files located in /Rapp folder (i.e. created by the RAPP app) are handled differently as their location data is not
    contained in specific-file-format metadata (e.g. exif for images) but instead the location is stored in Tapis
    metadata.

    This method is called by refresh_observable_projects()
    """
    user = session.query(User).get(userId)
    client = AgaveUtils(user)
    logger.info("Importing for project:{} directory:{}/{} for user:{}".format(projectId,
                                                                              systemId,
                                                                              path,
                                                                              user.username))
    try:
        listing = client.listing(systemId, path)
    except AgaveListingError:
        logger.exception(f"Unable to perform file listing on {systemId}/{path} when importing for project:{projectId}")
        NotificationsService.create(session, user, "error", f"Error importing as unable to access {systemId}/{path}")
        return

    # First item is always a reference to self
    files_in_directory = listing[1:]
    filenames_in_directory = [str(f.path) for f in files_in_directory]
    for item in files_in_directory:
        if item.type == "dir" and not str(item.path).endswith("/.Trash"):
            import_from_files_from_path(session, tenant_id, userId, systemId, item.path, projectId)
        item_system_path = os.path.join(systemId, str(item.path).lstrip("/"))
        if features_util.is_file_supported_for_automatic_scraping(item_system_path):
            try:
                # first check if there already is a file in the DB
                target_file = ImportsService.getImport(session, projectId, systemId, str(item.path))
                if target_file:
                    logger.debug(f"Already imported {item_system_path} for project:{projectId} so skipping. "
                                 f"The original import was on {target_file.created} and "
                                 f"successful_import={target_file.successful_import}")
                    continue

                # If it is a RApp project folder and not a questionnaire file, use the metadata from tapis meta service
                if features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata(item_system_path):
                    logger.info(f"RApp: importing:{item_system_path} for user:{user.username}. Using metadata service for geolocation.")
                    try:
                        meta = get_metadata_using_service_account(tenant_id, systemId, item.path)
                    except MissingServiceAccount:
                        logger.error(
                            "No service account. Unable to get metadata for {}:{}".format(systemId, item.path))
                        return {}

                    logger.debug("metadata from service account for file:{} : {}".format(item_system_path, meta))

                    if not meta:
                        logger.info("No metadata for {}; skipping file".format(item_system_path))
                        continue
                    geolocation = meta.get("geolocation")
                    if not geolocation:
                        logger.info("No geolocation for:{}; skipping".format(item_system_path))
                        continue
                    geolocation = parse_rapid_geolocation(geolocation)
                    tmp_file = client.getFile(systemId, item.path)
                    feat = FeaturesService.fromLatLng(session, projectId, geolocation, {})
                    feat.properties = meta
                    session.add(feat)
                    tmp_file.filename = Path(item.path).name
                    try:
                        FeaturesService.createFeatureAsset(session, projectId, feat.id, tmp_file, original_path=item_system_path)
                    except:  # noqa: E722
                        # remove newly-created placeholder feature if we fail to create an asset
                        FeaturesService.delete(session, feat.id)
                        raise RuntimeError("Unable to create feature asset")
                    NotificationsService.create(session, user, "success", "Imported {f}".format(f=item_system_path))
                    tmp_file.close()
                elif features_util.is_supported_for_automatic_scraping_without_metadata(item_system_path):
                    logger.info("importing:{} for user:{}".format(item_system_path, user.username))
                    tmp_file = client.getFile(systemId, item.path)
                    tmp_file.filename = Path(item.path).name
                    additional_files = get_additional_files(tmp_file, systemId, item.path, client, available_files=filenames_in_directory)

                    optional_location_from_metadata = get_geolocation_from_file_metadata(user, system_id=systemId, path=path)

                    FeaturesService.fromFileObj(session, projectId, tmp_file, {},
                                                original_path=item_system_path, additional_files=additional_files,
                                                location=optional_location_from_metadata)
                    NotificationsService.create(session, user, "success", "Imported {f}".format(f=item_system_path))
                    tmp_file.close()
                else:
                    # skipping as not supported
                    logger.debug("{path} is unsupported; skipping.".format(path=item_system_path))
                    continue
                import_state = ImportState.SUCCESS
            except Exception as e:
                NotificationsService.create(session, user, "error", "Error importing {f}".format(f=item_system_path))
                import_state = ImportState.FAILURE if e is not AgaveFileGetError else ImportState.RETRYABLE_FAILURE
                logger.exception(
                    f"Could not import for user:{user.username} from agave:{systemId}/{item_system_path} "
                    f"(while recursively importing files from {systemId}/{path}). "
                    f"retryable={import_state == ImportState.RETRYABLE_FAILURE}")
            if import_state != ImportState.RETRYABLE_FAILURE:
                try:
                    successful = True if import_state == ImportState.SUCCESS else False
                    # Save the row in the database that marks this file so we don't try to import it again
                    target_file = ImportsService.createImportedFile(projectId=projectId,
                                                                    systemId=systemId,
                                                                    path=str(item.path),
                                                                    lastUpdated=item.lastModified,
                                                                    successful_import=successful)
                    session.add(target_file)
                    session.commit()
                except Exception:  # noqa: E722
                    logger.exception(f"Failed to create db entry (imported_file)"
                                     f"for projectId:{projectId}  {systemId}/{path}")
                    raise


@app.task()
def refresh_observable_projects():
    """
    Refresh all observable projects
    """
    start_time = time.time()
    with create_task_session() as session:
        try:
            logger.info("Starting to refresh all observable projects")
            obs = session.query(ObservableDataProject).all()
            for i, o in enumerate(obs):
                # TODO_TAPISv3 refactored into a command (used here and by ProjectService) or just put into its own method for clarity?
                try:
                    try:
                        # we need a user with a jwt for importing
                        importing_user = next((u for u in o.project.users if u.jwt))
                        logger.info(f"Refreshing observable project ({i}/{len(obs)}): observer:{importing_user} "
                                    f"system:{o.system_id} path:{o.path} project:{o.project.id}")

                        # we need to add any users who have been added to the project/system or update if their admin-status
                        # has changed
                        current_users = set([SystemUser(username=u.user.username, admin=u.admin)
                                             for u in o.project.project_users])
                        updated_users = set(get_system_users(importing_user, o.system_id))

                        current_creator = session.query(ProjectUser)\
                            .filter(ProjectUser.project_id == o.id)\
                            .filter(ProjectUser.creator is True).one_or_none()

                        if current_users != updated_users:
                            logger.info("Updating users from:{} to:{}".format(current_users, updated_users))

                            # set project users
                            o.project.users = [UserService.getOrCreateUser(session, u.username, tenant=o.project.tenant_id)
                                               for u in updated_users]
                            session.add(o)
                            session.commit()

                            updated_users_to_admin_status = {u.username: u for u in updated_users}
                            logger.info("current_users_to_admin_status:{}".format(updated_users_to_admin_status))
                            for u in o.project.project_users:
                                u.admin = updated_users_to_admin_status[u.user.username].admin
                                session.add(u)
                            session.commit()

                            if current_creator:
                                # reset the creator by finding that updated user again and updating it.
                                current_creator = session.query(ProjectUser)\
                                    .filter(ProjectUser.project_id == o.id)\
                                    .filter(ProjectUser.user_id == current_creator.user_id)\
                                    .one_or_none()
                                if current_creator:
                                    current_creator.creator = True
                                    session.add(current_creator)
                                    session.commit()
                    except GetUsersForProjectNotSupported:
                        logger.info(f"Not updating users for project:{o.project.id} system_id:{o.system_id}")
                        pass

                    # perform the importing
                    if o.watch_content:
                        import_from_files_from_path(session, o.project.tenant_id, importing_user.id, o.system_id, o.path, o.project.id)
                except Exception:  # noqa: E722
                    logger.exception(f"Unhandled exception when importing observable project:{o.project.id}. "
                                     "Performing rollback of current database transaction")
                    session.rollback()
            total_time = time.time() - start_time
            logger.info("refresh_observable_projects completed. "
                        "Elapsed time {}".format(datetime.timedelta(seconds=total_time)))
        except Exception:  # noqa: E722
            logger.error("Error when trying to get list of observable projects; this is unexpected and should be reported"
                         "(i.e. https://jira.tacc.utexas.edu/browse/WG-131).")
            raise


if __name__ == "__main__":
    pass
