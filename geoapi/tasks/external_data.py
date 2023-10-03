import os
import concurrent
from pathlib import Path
import concurrent.futures
from enum import Enum
import time
import datetime
from celery import uuid as celery_uuid

from geoapi.celery_app import app
from geoapi.exceptions import InvalidCoordinateReferenceSystem, MissingServiceAccount
from geoapi.models import User, ProjectUser, ObservableDataProject, Task
from geoapi.utils.agave import (AgaveUtils, SystemUser, get_system_users, get_metadata_using_service_account,
                                AgaveFileGetError, AgaveListingError)
from geoapi.log import logger
from geoapi.services.features import FeaturesService
from geoapi.services.imports import ImportsService
from geoapi.services.vectors import SHAPEFILE_FILE_ADDITIONAL_FILES
import geoapi.services.point_cloud as pointcloud
from geoapi.tasks.lidar import convert_to_potree, check_point_cloud, get_point_cloud_info
from geoapi.db import create_task_session
from geoapi.services.notifications import NotificationsService
from geoapi.services.users import UserService


class ImportState(Enum):
    SUCCESS = 1
    FAILURE = 2
    RETRYABLE_FAILURE = 3


def _parse_rapid_geolocation(loc):
    coords = loc[0]
    lat = coords["latitude"]
    lon = coords["longitude"]
    return lat, lon


def is_member_of_rapp_project_folder(path):
    """
    Check to see if path is contained within RApp project folder
    :param path: str
    """
    return "/RApp/" in path


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


def get_additional_files(systemId: str, path: str, client, available_files=None):
    """
    Get any additional files needed for processing
    :param systemId: str
    :param path: str
    :param client
    :param available_files: list of files that exist (optional)
    :return: list of additional files
    """
    path = Path(path)
    if path.suffix.lower().lstrip('.') == "shp":
        paths_to_get = []
        for extension, required in SHAPEFILE_FILE_ADDITIONAL_FILES.items():
            additional_file_path = path.with_suffix(extension)
            if available_files and str(additional_file_path) not in available_files:
                if required:
                    logger.error("Could not import required shapefile-related file: "
                                 "agave: {} :: {}".format(systemId, additional_file_path))
                    raise Exception("Required file ({}) missing".format(additional_file_path))
                else:
                    continue
            paths_to_get.append(additional_file_path)

        additional_files = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            getting_files_futures = [executor.submit(get_file, client, systemId, additional_file_path, required)
                                     for additional_file_path in paths_to_get]
            for future in concurrent.futures.as_completed(getting_files_futures):
                _, additional_file_path, required, result_file, error = future.result()
                if not result_file and required:
                    logger.error("Could not import a required shapefile-related file: "
                                 "agave: {} :: {}   ---- error: {}".format(systemId, additional_file_path, error))
                if not result_file:
                    logger.debug("Unable to get non-required shapefile-related file: "
                                 "agave: {} :: {}".format(systemId, additional_file_path))
                    continue
                result_file.filename = Path(additional_file_path).name
                additional_files.append(result_file)
    else:
        additional_files = None
    return additional_files


@app.task(rate_limit="10/s")
def import_file_from_agave(userId: int, systemId: str, path: str, projectId: int):
    """
    Import file from TAPIS system

    Note: all geolocation information is expected to be embedded in the imported file.
    """
    with create_task_session() as session:
        try:
            user = session.query(User).get(userId)
            client = AgaveUtils(user.jwt)

            temp_file = client.getFile(systemId, path)
            temp_file.filename = Path(path).name
            additional_files = get_additional_files(systemId, path, client)
            FeaturesService.fromFileObj(session, projectId, temp_file, {},
                                        original_path=path, additional_files=additional_files)
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
        client = AgaveUtils(user.jwt)

        point_cloud = pointcloud.PointCloudService.get(session, pointCloudId)
        celery_task_id = celery_uuid()

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
                logger.error("Could not import point cloud file due to missing"
                             " coordinate reference system: {}:{}".format(system_id, path))
                failed_message = 'Error importing {}: missing coordinate reference system'.format(path)
            except Exception as e:
                logger.error("Could not import point cloud file for user:{} from tapis: {}/{} : {}".format(user.username,
                                                                                                           system_id,
                                                                                                           path, e))
                failed_message = 'Unknown error importing {}:{}'.format(system_id, path)

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
        with create_task_session() as database_session:
            user = session.query(User).get(userId)
            NotificationsService.create(database_session,
                                        user,
                                        "success",
                                        "Completed potree converter (for point cloud {}).".format(pointCloudId))
    except:  # noqa: E722
        with create_task_session() as database_session:
            user = session.query(User).get(userId)
            logger.exception("point cloud:{} conversion failed for user:{}".format(pointCloudId, user.username))
            _update_point_cloud_task(database_session, pointCloudId, description="", status="FAILED")
            NotificationsService.create(database_session, user, "error", "Processing failed for point cloud ({})!".format(pointCloudId))
        return


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
    client = AgaveUtils(user.jwt)
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
        # skip any junk files that are not allowed
        if item.path.suffix.lower().lstrip('.') not in FeaturesService.ALLOWED_EXTENSIONS:
            continue
        else:
            item_system_path = os.path.join(item.system, str(item.path).lstrip("/"))
            try:
                # first check if there already is a file in the DB
                target_file = ImportsService.getImport(session, projectId, systemId, str(item.path))
                if target_file:
                    logger.debug(f"Already imported {item_system_path} for project:{projectId} so skipping. "
                                 f"The original import was on {target_file.created} and "
                                 f"successful_import={target_file.successful_import}")
                    continue

                # If it is a RApp project folder, grab the metadata from tapis meta service
                if is_member_of_rapp_project_folder(item_system_path):
                    logger.info("RApp: importing:{} for user:{}".format(item_system_path, user.username))
                    if item.path.suffix.lower().lstrip(
                            '.') not in FeaturesService.ALLOWED_GEOSPATIAL_FEATURE_ASSET_EXTENSIONS:
                        logger.info("{path} is unsupported; skipping.".format(path=item_system_path))
                        continue

                    logger.info("{} {} {}".format(item_system_path, item.system, item.path))

                    try:
                        meta = get_metadata_using_service_account(tenant_id, item.system, item.path)
                    except MissingServiceAccount:
                        logger.error(
                            "No service account. Unable to get metadata for {}:{}".format(item.system, item.path))
                        return {}

                    logger.debug("metadata from service account for file:{} : {}".format(item_system_path, meta))

                    if not meta:
                        logger.info("No metadata for {}; skipping file".format(item_system_path))
                        continue
                    geolocation = meta.get("geolocation")
                    if not geolocation:
                        logger.info("No geolocation for:{}; skipping".format(item_system_path))
                        continue
                    lat, lon = _parse_rapid_geolocation(geolocation)
                    tmp_file = client.getFile(systemId, item.path)
                    feat = FeaturesService.fromLatLng(session, projectId, lat, lon, {})
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
                elif item.path.suffix.lower().lstrip('.') in FeaturesService.ALLOWED_GEOSPATIAL_EXTENSIONS:
                    logger.info("importing:{} for user:{}".format(item_system_path, user.username))
                    tmp_file = client.getFile(systemId, item.path)
                    tmp_file.filename = Path(item.path).name
                    additional_files = get_additional_files(systemId, item.path, client, filenames_in_directory)
                    FeaturesService.fromFileObj(session, projectId, tmp_file, {},
                                                original_path=item_system_path, additional_files=additional_files)
                    NotificationsService.create(session, user, "success", "Imported {f}".format(f=item_system_path))
                    tmp_file.close()
                else:
                    continue
                import_state = ImportState.SUCCESS
            except Exception as e:
                logger.error(
                    f"Could not import for user:{user.username} from agave:{systemId}/{item_system_path} "
                    f"(while recursively importing files from {systemId}/{path})")
                NotificationsService.create(session, user, "error", "Error importing {f}".format(f=item_system_path))
                import_state = ImportState.FAILURE if e is not AgaveFileGetError else ImportState.RETRYABLE_FAILURE
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
                try:
                    # we need a user with a jwt for importing
                    importing_user = next((u for u in o.project.users if u.jwt))
                    logger.info(f"Refreshing observable project ({i}/{len(obs)}): observer:{importing_user} "
                                f"system:{o.system_id} path:{o.path} project:{o.project.id}")

                    # we need to add any users who have been added to the project/system or update if their admin-status
                    # has changed
                    current_users = set([SystemUser(username=u.user.username, admin=u.admin)
                                         for u in o.project.project_users])
                    updated_users = set(get_system_users(o.project.tenant_id, importing_user.jwt, o.system_id))

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
