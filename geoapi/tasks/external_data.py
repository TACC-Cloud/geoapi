import os
import concurrent
from pathlib import Path
import concurrent.futures
from enum import Enum
import json
import time
import datetime

from geoapi.celery_app import app
from geoapi.exceptions import InvalidCoordinateReferenceSystem, MissingServiceAccount
from geoapi.models import User, ObservableDataProject, Task, Feature, FeatureAsset 
from geoapi.utils.agave import AgaveUtils, get_system_users, get_metadata_using_service_account, AgaveFileGetError
from geoapi.log import logger
from geoapi.services.features import FeaturesService
from geoapi.services.imports import ImportsService
from geoapi.services.vectors import SHAPEFILE_FILE_ADDITIONAL_FILES
import geoapi.services.point_cloud as pointcloud
from geoapi.tasks.lidar import convert_to_potree, check_point_cloud, get_point_cloud_info
from geoapi.db import db_session
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
    except Exception as e:
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


@app.task(rate_limit="1/s")
def import_file_from_agave(userId: int, systemId: str, path: str, projectId: int):
    user = db_session.query(User).get(userId)
    client = AgaveUtils(user.jwt)
    try:
        tmpFile = client.getFile(systemId, path)
        tmpFile.filename = Path(path).name
        additional_files = get_additional_files(systemId, path, client)
        FeaturesService.fromFileObj(projectId, tmpFile, {}, original_path=path, additional_files=additional_files)
        NotificationsService.create(user, "success", "Imported {f}".format(f=path))
        tmpFile.close()
    except Exception as e:
        db_session.rollback()
        logger.exception("Could not import file from agave: {} :: {}".format(systemId, path))
        NotificationsService.create(user, "error", "Error importing {f}".format(f=path))
        raise e



def _update_point_cloud_task(pointCloudId: int, description: str = None, status: str = None):
    task = pointcloud.PointCloudService.get(pointCloudId).task
    if description is not None:
        task.description = description
    if status is not None:
        task.status = status
    try:
        db_session.add(task)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


@app.task(rate_limit="1/s")
def import_point_clouds_from_agave(userId: int, files, pointCloudId: int):
    user = db_session.query(User).get(userId)
    client = AgaveUtils(user.jwt)

    point_cloud = pointcloud.PointCloudService.get(pointCloudId)
    celery_task_id = celery_uuid()

    task = Task()
    task.process_id = celery_task_id
    task.status = "RUNNING"

    point_cloud.task = task
    db_session.add(point_cloud)

    new_asset_files = []
    failed_message = None
    for file in files:
        _update_point_cloud_task(pointCloudId,
                                 description="Importing file ({}/{})".format(len(new_asset_files) + 1, len(files)))

        NotificationsService.create(user, "success", task.description)

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
            check_point_cloud.apply(args=[file_path], throw=True)

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
            _update_point_cloud_task(pointCloudId, description=failed_message, status="FAILED")
            NotificationsService.create(user, "error", failed_message)
            return

    _update_point_cloud_task(pointCloudId, description="Running potree converter", status="RUNNING")

    point_cloud.files_info = json.dumps(get_point_cloud_info(pointCloudId))
    try:
        db_session.add(point_cloud)
        db_session.add(task)
        db_session.commit()
    except:
        db_session.rollback()
        raise
    NotificationsService.create(user,
                                "success",
                                "Running potree converter (for point cloud {}).".format(pointCloudId))

    try:
        convert_to_potree.apply(args=[pointCloudId], task_id=celery_task_id, throw=True)
        NotificationsService.create(user,
                                    "success",
                                    "Completed potree converter (for point cloud {}).".format(pointCloudId))
    except:
        logger.exception("point cloud:{} conversion failed for user:{}".format(pointCloudId, user.username))
        _update_point_cloud_task(pointCloudId, description="", status="FAILED")
        NotificationsService.create(user, "error", "Processing failed for point cloud ({})!".format(pointCloudId))
        return


@app.task(rate_limit="5/s")
def import_from_agave(tenant_id: str, userId: int, systemId: str, path: str, projectId: int):
    user = db_session.query(User).get(userId)
    client = AgaveUtils(user.jwt)
    logger.info("Importing for project:{} directory:{}/{} for user:{}".format(projectId,
                                                                              systemId,
                                                                              path,
                                                                              user.username))
    listing = client.listing(systemId, path)
    # First item is always a reference to self
    files_in_directory = listing[1:]
    filenames_in_directory = [str(f.path) for f in files_in_directory]
    for item in files_in_directory:
        if item.type == "dir" and not str(item.path).endswith("/.Trash"):
            import_from_agave(tenant_id, userId, systemId, item.path, projectId)
        # skip any junk files that are not allowed
        if item.path.suffix.lower().lstrip('.') not in FeaturesService.ALLOWED_EXTENSIONS:
            continue
        else:
            try:
                # first check if there already is a file in the DB
                item_system_path = os.path.join(item.system, str(item.path).lstrip("/"))
                target_file = ImportsService.getImport(projectId, systemId, str(item.path))
                if target_file:
                    logger.debug(f"Already imported {item_system_path} for project:{projectId} so skipping. "
                                 f"The original import was on {target_file.created} and "
                                 f"successful_import={target_file.successful_import}")
                    continue

                # If its a RApp project folder, grab the metadata from tapis meta service
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
                    tmpFile = client.getFile(systemId, item.path)
                    feat = FeaturesService.fromLatLng(projectId, lat, lon, {})
                    feat.properties = meta
                    db_session.add(feat)
                    tmpFile.filename = Path(item.path).name
                    try:
                        FeaturesService.createFeatureAsset(projectId, feat.id, tmpFile, original_path=item_system_path)
                    except:
                        # remove newly-created placeholder feature if we fail to create an asset
                        FeaturesService.delete(feat.id)
                        raise RuntimeError("Unable to create feature asset")
                    NotificationsService.create(user, "success", "Imported {f}".format(f=item_system_path))
                    tmpFile.close()
                elif item.path.suffix.lower().lstrip('.') in FeaturesService.ALLOWED_GEOSPATIAL_EXTENSIONS:
                    logger.info("importing:{} for user:{}".format(item_system_path, user.username))
                    tmpFile = client.getFile(systemId, item.path)
                    tmpFile.filename = Path(item.path).name
                    additional_files = get_additional_files(systemId, item.path, client, filenames_in_directory)
                    FeaturesService.fromFileObj(projectId, tmpFile, {},
                                                original_path=item_system_path, additional_files=additional_files)
                    NotificationsService.create(user, "success", "Imported {f}".format(f=item_system_path))
                    tmpFile.close()
                else:
                    continue
                import_state = ImportState.SUCCESS
            except Exception as e:
                db_session.rollback()
                logger.error(
                    "Could not import for user:{} from agave:{}/{}".format(user.username, systemId, path))
                NotificationsService.create(user, "error", "Error importing {f}".format(f=item_system_path))
                import_state = ImportState.FAILURE if e is not AgaveFileGetError else ImportState.RETRYABLE_FAILURE
                logger.exception(e)
            if import_state != ImportState.RETRYABLE_FAILURE:
                try:
                    successful = True if import_state == ImportState.SUCCESS else False
                    # Save the row in the database that marks this file so we don't try to import it again
                    target_file = ImportsService.createImportedFile(projectId=projectId,
                                                                    systemId=systemId,
                                                                    path=str(item.path),
                                                                    lastUpdated=item.lastModified,
                                                                    successful_import=successful)
                    db_session.add(target_file)
                    db_session.commit()
                except Exception as e:
                    logger.exception(f"Failed to create db entry (imported_file)"
                                     f"for projectId:{projectId}  {systemId}/{path}")
                    db_session.rollback()


@app.task()
def refresh_observable_projects():
    start_time = time.time()
    try:
        obs = db_session.query(ObservableDataProject).all()
        for i, o in enumerate(obs):
            # we need a user with a jwt for importing
            importing_user = next((u for u in o.project.users if u.jwt))
            logger.info("Refreshing observable project ({}/{}): observer:{} system:{} path:{}".format(i,
                                                                                                      len(obs),
                                                                                                      importing_user,
                                                                                                      o.system_id,
                                                                                                      o.path))
            current_user_names = set([u.username for u in o.project.users])

            # we need to add any users who have been added to the system roles
            # (note that we do not delete any that are no longer listed on system roles; we only add users)
            system_users = set(get_system_users(o.project.tenant_id, importing_user.jwt, o.system_id))
            updated_user_names = system_users.union(current_user_names)
            if updated_user_names != current_user_names:
                logger.info("Updating to add the following users:{}   "
                            "Updated user list is now: {}".format(updated_user_names - current_user_names,
                                                                  updated_user_names))
                o.project.users = [UserService.getOrCreateUser(u, tenant=o.project.tenant_id)
                                   for u in updated_user_names]
                db_session.add(o)
                db_session.commit()

            # perform the importing
            if o.watch_content:
                import_from_agave(o.project.tenant_id, importing_user.id, o.system_id, o.path, o.project.id)
    except Exception:
        logger.exception("Unhandled exception when importing observable project")
        db_session.rollback()

    total_time = time.time() - start_time
    logger.info(f"{total_time}")
    logger.info("refresh_observable_projects completed. "
                "Elapsed time {}".format(datetime.timedelta(seconds=total_time)))


if __name__ == "__main__":
    pass
