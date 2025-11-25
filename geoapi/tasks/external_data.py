import os
import json
import time
import datetime
import concurrent
import concurrent.futures
from pathlib import Path
from enum import Enum

from celery import current_task
from sqlalchemy import true

from geoapi.celery_app import app
from geoapi.exceptions import (
    GetUsersForProjectNotSupported,
)
from geoapi.models import Project, User, ProjectUser
from geoapi.utils.external_apis import (
    TapisUtils,
    SystemUser,
    get_system_users,
    get_metadata,
    TapisFileGetError,
    TapisListingError,
)
from geoapi.utils import features as features_util
from geoapi.log import logger
from geoapi.services.features import FeaturesService
from geoapi.services.imports import ImportsService
from geoapi.services.vectors import SHAPEFILE_FILE_ADDITIONAL_FILES
from geoapi.db import create_task_session
from geoapi.services.users import UserService
from geoapi.utils.additional_file import AdditionalFile
from geoapi.utils.geo_location import (
    parse_rapid_geolocation,
    get_geolocation_from_file_metadata,
)
from geoapi.tasks.utils import send_progress_update


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


def get_additional_files(
    current_file, system_id: str, path: str, client, available_files=None
):
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
    file_suffix = current_file_path.suffix.lower().lstrip(".")
    if file_suffix == "shp":
        logger.info(
            f"Determining which shapefile-related files need to be downloaded for file {current_file.filename}"
        )
        for extension, required in SHAPEFILE_FILE_ADDITIONAL_FILES.items():
            additional_file_path = current_file_path.with_suffix(extension)
            if available_files and str(additional_file_path) not in available_files:
                if required:
                    logger.error(
                        f"Could not import required shapefile-related file: tapis: {system_id}/{additional_file_path}"
                    )
                    raise Exception(
                        f"Required file ({system_id}/{additional_file_path}) missing"
                    )
                else:
                    continue
            additional_files_to_get.append(
                AdditionalFile(path=additional_file_path, required=required)
            )
    elif file_suffix == "rq":
        logger.info(
            f"Parsing rq file {current_file.filename} to see what assets need to be downloaded "
        )
        data = json.load(current_file)
        for section in data["sections"]:
            for question in section["questions"]:
                for asset in question.get("assets", []):
                    # determine full path for this asset and add to list
                    additional_file_path = current_file_path.with_name(
                        asset["filename"]
                    )
                    additional_files_to_get.append(
                        AdditionalFile(path=additional_file_path, required=True)
                    )
        logger.info(
            f"{len(additional_files_to_get)} assets were found for rq file {current_file.filename}"
        )

        # Seek back to start of file
        current_file.seek(0)
    else:
        # No additional files needed for this file type
        return None

    # Try to get all additional files.
    additional_files_result = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        getting_files_futures = [
            executor.submit(
                get_file,
                client,
                system_id,
                additional_file.path,
                additional_file.required,
            )
            for additional_file in additional_files_to_get
        ]
        for future in concurrent.futures.as_completed(getting_files_futures):
            _, additional_file_path, required, result_file, error = future.result()
            if not result_file and required:
                logger.error(
                    f"Could not import a required {file_suffix}-related file: "
                    f"tapis: {system_id} :: {additional_file_path}   ---- error: {error}"
                )
                raise Exception(
                    f"Required file ({system_id}/{additional_file_path}) missing"
                )
            if not result_file:
                logger.error(
                    f"Unable to get non-required {file_suffix}-related file: "
                    f"tapis: {system_id} :: {additional_file_path}   ---- error: {error}"
                )

                continue
            logger.debug(
                f"Finished getting {file_suffix}-related file: ({system_id}/{additional_file_path}"
            )
            result_file.filename = Path(additional_file_path).name
            additional_files_result.append(result_file)
    return additional_files_result


@app.task(rate_limit="10/s")
def import_file_from_tapis(userId: int, systemId: str, path: str, projectId: int):
    """
    Import file from TAPIS system

    Tapis metdata is checked for location information. If no Tapis metadata, then geolocation information is
    expected to be embedded in the imported file.
    """
    with create_task_session() as session:
        task_id = current_task.request.id
        try:
            user = session.get(User, userId)
            client = TapisUtils(session, user)
            temp_file = client.getFile(systemId, path)
            temp_file.filename = Path(path).name
            additional_files = get_additional_files(temp_file, systemId, path, client)

            optional_location_from_metadata = get_geolocation_from_file_metadata(
                session, user, system_id=systemId, path=path
            )

            FeaturesService.fromFileObj(
                session,
                projectId,
                temp_file,
                {},
                original_system=systemId,
                original_path=path,
                additional_files=additional_files,
                location=optional_location_from_metadata,
            )
            send_progress_update(
                user, task_id, "success", f"Imported {path} successfully"
            )
            temp_file.close()
        except Exception:  # noqa: E722
            logger.exception(
                "Could not import file from tapis: %s :: %s", systemId, path
            )
            send_progress_update(user, task_id, "error", f"Error importing {path}")
            raise


@app.task(rate_limit="5/s")
def import_from_tapis(
    tenant_id: str, userId: int, systemId: str, path: str, projectId: int
):
    """
    Recursively import files from a system/path.

    For projects where watch_content is True, this method is called periodically by refresh_projects_watch_content()
    and once when the project is initially created (if watch_content is True)
    """
    with create_task_session() as session:
        import_files_recursively_from_path(
            session, tenant_id, userId, systemId, path, projectId
        )


def import_files_recursively_from_path(
    session, tenant_id: str, userId: int, systemId: str, path: str, projectId: int
):
    """
    Recursively import files from a system/path.

    If file has already been imported (i.e. during a previous call), we don't re-import it. Likewise,
    if we have previously failed at importing a file, we do not retry to import the file (unless it was an error like
    file-access where it makes sense to retry at a later time).

    Files located in /Rapp folder (i.e. created by the RAPP app) are handled differently as their location data is not
    contained in specific-file-format metadata (e.g. exif for images) but instead the location is stored in Tapis
    metadata.

    This method is called by refresh_projects_watch_content() via import_from_tapis
    """
    user = session.get(User, userId)
    logger.info(
        "Importing for project:{} directory:{}/{} for user:{}".format(
            projectId, systemId, path, user.username
        )
    )
    client = TapisUtils(session, user)

    try:
        listing = client.listing(systemId, path)
    except TapisListingError:
        logger.exception(
            f"Unable to perform file listing on {systemId}/{path} when importing for project:{projectId}"
        )
        send_progress_update(
            user,
            current_task.request.id,
            "error",
            f"Error importing as unable to access {systemId}/{path}",
        )
        return
    filenames_in_directory = [str(f.path) for f in listing]
    for item in listing:
        if item.type == "dir" and not str(item.path).endswith(".Trash"):
            import_files_recursively_from_path(
                session, tenant_id, userId, systemId, item.path, projectId
            )
        item_system_path = os.path.join(systemId, str(item.path).lstrip("/"))
        if features_util.is_file_supported_for_automatic_scraping(item_system_path):
            try:
                # first check if there already is a file in the DB
                target_file = ImportsService.getImport(
                    session, projectId, systemId, str(item.path)
                )
                if target_file:
                    logger.debug(
                        f"Already imported {item_system_path} for project:{projectId} so skipping. "
                        f"The original import was on {target_file.created} and "
                        f"successful_import={target_file.successful_import}"
                    )
                    continue

                # If it is a RApp project folder and not a questionnaire file, use the metadata from tapis meta service
                if features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata(
                    item_system_path
                ):
                    logger.info(
                        f"RApp: importing:{item_system_path} for user:{user.username}. Using metadata service for geolocation."
                    )
                    meta = get_metadata(session, user, systemId, item.path)

                    logger.debug(
                        "metadata from service account for file:{} : {}".format(
                            item_system_path, meta
                        )
                    )

                    if not meta:
                        logger.info(
                            "No metadata for {}; skipping file".format(item_system_path)
                        )
                        continue
                    geolocation = meta.get("geolocation")
                    if not geolocation:
                        logger.info(
                            "No geolocation for:{}; skipping".format(item_system_path)
                        )
                        continue
                    geolocation = parse_rapid_geolocation(geolocation)
                    tmp_file = client.getFile(systemId, item.path)
                    feat = FeaturesService.fromLatLng(
                        session, projectId, geolocation, {}
                    )
                    feat.properties = meta
                    session.add(feat)
                    tmp_file.filename = Path(item.path).name
                    try:
                        FeaturesService.createFeatureAsset(
                            session,
                            projectId,
                            feat.id,
                            tmp_file,
                            original_system=systemId,
                            original_path=item_system_path,
                        )
                    except:  # noqa: E722
                        # remove newly-created placeholder feature if we fail to create an asset
                        FeaturesService.delete(session, feat.id)
                        raise RuntimeError("Unable to create feature asset")
                    send_progress_update(
                        user,
                        current_task.request.id,
                        "success",
                        "Imported {f}".format(f=item_system_path),
                    )
                    tmp_file.close()
                elif features_util.is_supported_for_automatic_scraping_without_metadata(
                    item_system_path
                ):
                    logger.info(
                        "importing:{} for user:{}".format(
                            item_system_path, user.username
                        )
                    )
                    tmp_file = client.getFile(systemId, item.path)
                    tmp_file.filename = Path(item.path).name
                    additional_files = get_additional_files(
                        tmp_file,
                        systemId,
                        item.path,
                        client,
                        available_files=filenames_in_directory,
                    )

                    optional_location_from_metadata = (
                        get_geolocation_from_file_metadata(
                            session, user, system_id=systemId, path=path
                        )
                    )

                    FeaturesService.fromFileObj(
                        session,
                        projectId,
                        tmp_file,
                        {},
                        original_system=systemId,
                        original_path=path,
                        additional_files=additional_files,
                        location=optional_location_from_metadata,
                    )
                    send_progress_update(
                        user,
                        current_task.request.id,
                        "success",
                        "Imported {f}".format(f=item_system_path),
                    )
                    tmp_file.close()
                else:
                    # skipping as not supported
                    logger.debug(
                        "{path} is unsupported; skipping.".format(path=item_system_path)
                    )
                    continue
                import_state = ImportState.SUCCESS
            except Exception as e:
                send_progress_update(
                    user,
                    current_task.request.id,
                    "error",
                    "Error importing {f}".format(f=item_system_path),
                )
                import_state = (
                    ImportState.FAILURE
                    if e is not TapisFileGetError
                    else ImportState.RETRYABLE_FAILURE
                )
                logger.exception(
                    f"Could not import for user:{user.username} from tapis:{systemId}/{item_system_path} "
                    f"(while recursively importing files from {systemId}/{path}). "
                    f"retryable={import_state == ImportState.RETRYABLE_FAILURE}"
                )
            if import_state != ImportState.RETRYABLE_FAILURE:
                try:
                    successful = True if import_state == ImportState.SUCCESS else False
                    # Save the row in the database that marks this file so we don't try to import it again
                    target_file = ImportsService.createImportedFile(
                        projectId=projectId,
                        systemId=systemId,
                        path=str(item.path),
                        lastUpdated=item.lastModified,
                        successful_import=successful,
                    )
                    session.add(target_file)
                    session.commit()
                except Exception:  # noqa: E722
                    logger.exception(
                        f"Failed to create db entry (imported_file)"
                        f"for projectId:{projectId}  {systemId}/{path}"
                    )
                    raise


def _get_user_with_valid_token(project):
    """Return a user with valid token

    Returns None if no such user exists.
    """
    importing_user = next(
        (
            user
            for user in project.users
            if user.has_unexpired_refresh_token() or user.has_valid_token()
        ),
        None,
    )
    return importing_user


@app.task()
def refresh_projects_watch_content():
    """
    Refresh users for all projects where watch_content is True
    """
    start_time = time.time()
    with create_task_session() as session:
        try:
            logger.info("Starting to refresh all projects where watch_content is True")
            projects_with_watch_content = (
                session.query(Project).filter(Project.watch_content.is_(true())).all()
            )
            for i, project in enumerate(projects_with_watch_content):
                try:
                    importing_user = _get_user_with_valid_token(project)

                    if importing_user is None:
                        logger.error(
                            f"Unable to watch content of project"
                            f" ({i}/{len(projects_with_watch_content)}): observer:{importing_user} "
                            f"system:{project.system_id} path:{project.system_path} project:{project.id} "
                            f"watch_content:{project.watch_content}: No user with an active token found. "
                            f"So we are skipping (i.e. no update of users or importing of watched "
                            f"content)"
                        )
                        continue

                    # perform the importing
                    if project.watch_content:
                        logger.info(
                            f"Refreshing content of project ({i}/{len(projects_with_watch_content)}): "
                            f"observer:{importing_user} system:{project.system_id} path:{project.system_path} "
                            f"project:{project.id} watch_content:{project.watch_content}"
                        )
                        import_files_recursively_from_path(
                            session,
                            project.tenant_id,
                            importing_user.id,
                            project.system_id,
                            project.system_path,
                            project.id,
                        )
                except Exception:  # noqa: E722
                    logger.exception(
                        f"Unhandled exception when importing for project:{project.id}. "
                        "Performing rollback of current database transaction"
                    )
                    session.rollback()
            total_time = time.time() - start_time
            logger.info(
                "refresh_projects_watch_content completed. "
                "Elapsed time {}".format(datetime.timedelta(seconds=total_time))
            )
        except Exception:  # noqa: E722
            logger.error(
                "Error when trying to get list of projects where watch_content is True; "
                "this is unexpected and should be reported "
                "(i.e. https://jira.tacc.utexas.edu/browse/WG-131)."
            )
            raise


@app.task()
def refresh_projects_watch_users():
    """
    Refresh users for all projects where watch_users is True
    """
    start_time = time.time()
    with create_task_session() as session:
        try:
            logger.info("Starting to refresh all projects where watch_users is True")
            projects_with_watch_users = (
                session.query(Project).filter(Project.watch_users.is_(true())).all()
            )
            for i, project in enumerate(projects_with_watch_users):
                # TODO_TAPISv3 refactored into a command (used here and by ProjectService)
                # or just put into its own method for clarity?
                try:
                    # we need a user with a valid Tapis token for importing files or updating users
                    importing_user = next(
                        (
                            user
                            for user in project.users
                            if user.has_unexpired_refresh_token()
                            or user.has_valid_token()
                        ),
                        None,
                    )

                    if importing_user is None:
                        logger.error(
                            f"Unable to watch users of project"
                            f" ({i}/{len(projects_with_watch_users)}): observer:{importing_user} "
                            f"system:{project.system_id} path:{project.system_path} project:{project.id} "
                            f"watch_content:{project.watch_content}: No user with an active token found. "
                            f"So we are skipping (i.e. no update of users or importing of watched "
                            f"content)"
                        )
                        continue

                    logger.info(
                        f"Refreshing users of project ({i}/{len(projects_with_watch_users)}): "
                        f"observer:{importing_user} system:{project.system_id} path:{project.system_path} "
                        f"project:{project.id} watch_content:{project.watch_content}"
                    )

                    # we need to add any users who have been added to the project/system or update
                    # if their admin-status has changed
                    current_users = set(
                        [
                            SystemUser(
                                username=project_user.user.username,
                                admin=project_user.admin,
                            )
                            for project_user in project.project_users
                        ]
                    )
                    updated_users = set(
                        get_system_users(session, importing_user, project.system_id)
                    )

                    current_creator = (
                        session.query(ProjectUser)
                        .filter(ProjectUser.project_id == project.id)
                        .filter(ProjectUser.creator is True)
                        .one_or_none()
                    )
                    if current_users != updated_users:
                        logger.info(
                            "Updating users from:{} to:{}".format(
                                current_users, updated_users
                            )
                        )

                        # set project users
                        project.users = [
                            UserService.getOrCreateUser(
                                session, user.username, tenant=project.tenant_id
                            )
                            for user in updated_users
                        ]
                        session.add(project)
                        session.commit()

                        updated_users_to_admin_status = {
                            user.username: user for user in updated_users
                        }
                        logger.info(
                            "current_users_to_admin_status:{}".format(
                                updated_users_to_admin_status
                            )
                        )
                        for project_user in project.project_users:
                            project_user.admin = updated_users_to_admin_status[
                                project_user.user.username
                            ].admin
                            session.add(project_user)
                        session.commit()

                        if current_creator:
                            # reset the creator by finding that updated user again and updating it.
                            current_creator = (
                                session.query(ProjectUser)
                                .filter(ProjectUser.project_id == project.id)
                                .filter(ProjectUser.user_id == current_creator.user_id)
                                .one_or_none()
                            )
                            if current_creator:
                                current_creator.creator = True
                                session.add(current_creator)
                                session.commit()
                except GetUsersForProjectNotSupported:
                    logger.info(
                        f"Not updating users for project:{project.id} "
                        f"system_id:{project.system_id}"
                    )
                    pass
                except Exception:  # noqa: E722
                    logger.exception(
                        f"Unhandled exception when updating users for project:{project.id}. "
                        "Performing rollback of current database transaction"
                    )
                    session.rollback()
            total_time = time.time() - start_time
            logger.info(
                "refresh_projects_watch_users completed. "
                "Elapsed time {}".format(datetime.timedelta(seconds=total_time))
            )
        except Exception:  # noqa: E722
            logger.error(
                "Error when trying to get list of projects where watch_users is True; "
                "this is unexpected and should be reported "
                "(i.e. https://jira.tacc.utexas.edu/browse/WG-131)."
            )
            raise


if __name__ == "__main__":
    pass
