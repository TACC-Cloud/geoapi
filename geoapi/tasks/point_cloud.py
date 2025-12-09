import os
import uuid
import subprocess
import pathlib
import re
import shutil
from geoalchemy2.shape import from_shape
import celery


from geoapi.log import logging

from geoapi.tasks.utils import GeoAPITask, send_progress_update
from geoapi.celery_app import app
from geoapi.db import create_task_session
from geoapi.models import Task, TaskStatus, User
from geoapi.utils.assets import (
    make_project_asset_dir,
    get_asset_path,
    get_asset_relative_path,
)
from geoapi.utils.external_apis import TapisUtils
from geoapi.utils.point_cloud import getProj4, get_bounding_box_2d
from geoapi.utils.geometries import convert_3D_2D
from geoapi.exceptions import InvalidCoordinateReferenceSystem
from geoapi.services.point_cloud import PointCloudService


logger = logging.getLogger(__file__)


def get_point_cloud_files(path):
    """
    Get all point cloud files in a path
    :param path: strings
    :return: list of file paths of point cloud files
    """
    from geoapi.services.point_cloud import PointCloudService

    input_files = [
        get_asset_path(path, file)
        for file in os.listdir(path)
        if pathlib.Path(file).suffix.lstrip(".").lower()
        in PointCloudService.POINT_CLOUD_FILE_EXTENSIONS
    ]
    return input_files


def check_point_cloud(file_path: str) -> None:
    """
    Check point cloud file that it has required info
    :param file_path: str
    :return: None
    :raises InvalidCoordinateReferenceSystem: if file missing crs
    """
    # TODO make this a check about if we have enough info ect.
    getProj4(file_path)


def get_point_cloud_info(files: list) -> list:
    """
    Get info from source files
    """
    return [
        {
            "original_system": file["system"],
            "original_path": file["path"],
            "name": os.path.basename(file["path"]),
        }
        for file in files
    ]


class PointCloudConversionException(Exception):
    def __init__(self, message="Unknown error"):
        self.message = message
        super().__init__(self.message)


def run_potree_converter(
    pointCloudId,
    path_to_original_point_clouds,
    path_temp_processed_point_cloud_path,
    conversion_parameters=None,
):
    """Run potree converter as external process"""
    command = [
        "/opt/PotreeConverter/build/PotreeConverter",
        "--verbose",
        "-i",
        path_to_original_point_clouds,
        "-o",
        path_temp_processed_point_cloud_path,
        "--overwrite",
        "--generate-page",
        "index",
    ]
    if conversion_parameters:
        command.extend(conversion_parameters.split())
    logger.info(
        "Processing point cloud (#{}).  command:{}".format(
            pointCloudId, " ".join(command)
        )
    )
    subprocess.run(command, check=True, capture_output=True, text=True)


@app.task(bind=True, base=GeoAPITask)
def convert_to_potree(self, pointCloudId: int) -> None:
    """
    Use the potree converter to convert a LAS/LAZ file to potree format

    Note: this operation is memory-intensive and time-consuming.  Large LAS files (>8 Gb) can use >50gb of memory.

    if process killed (e.g. due to memory constraints), PointCloudTaskException is raised

    :param pointCloudId: int
    :param userId: int
    :return: None
    :raises PointCloudTaskException: if conversion fails
    """
    from geoapi.models import Feature, FeatureAsset
    from geoapi.services.point_cloud import PointCloudService

    with create_task_session() as session:
        point_cloud = PointCloudService.get(session, pointCloudId)
        conversion_parameters = point_cloud.conversion_parameters
        path_to_original_point_clouds = get_asset_path(
            point_cloud.path, PointCloudService.ORIGINAL_FILES_DIR
        )
        path_temp_processed_point_cloud_path = get_asset_path(
            point_cloud.path, PointCloudService.PROCESSED_DIR
        )

    input_files = get_point_cloud_files(path_to_original_point_clouds)

    outline = get_bounding_box_2d(input_files)

    try:
        run_potree_converter(
            pointCloudId,
            path_to_original_point_clouds,
            path_temp_processed_point_cloud_path,
            conversion_parameters,
        )
    except subprocess.CalledProcessError as e:
        error_description = "Point cloud conversion failed"
        if e.returncode == -9:  # SIGKILL; most likely ran out of memory
            error_description += "; process killed due to insufficient memory"
        logger.exception(
            f"Processing point cloud failed (point_cloud:{pointCloudId} "
            f"path_to_original_point_clouds:{path_to_original_point_clouds} )."
        )
        raise PointCloudConversionException(error_description)

    with create_task_session() as session:
        point_cloud = PointCloudService.get(session, pointCloudId)
        # Create preview viewer html (with no menu and now nsf logo)
        with open(
            os.path.join(path_temp_processed_point_cloud_path, "preview.html"), "w+"
        ) as preview:
            with open(
                os.path.join(path_temp_processed_point_cloud_path, "index.html"), "r"
            ) as viewer:
                content = viewer.read()
                content = re.sub(
                    r"<div class=\"nsf_logo\"(.+?)</div>", "", content, flags=re.DOTALL
                )
                content = content.replace(
                    "viewer.toggleSidebar()", "$('.potree_menu_toggle').hide()"
                )
                preview.write(content)

            if point_cloud.feature_id:
                feature = point_cloud.feature
            else:
                feature = Feature()
                feature.project_id = point_cloud.project_id

                asset_uuid = uuid.uuid4()
                base_filepath = make_project_asset_dir(point_cloud.project_id)
                asset_path = os.path.join(base_filepath, str(asset_uuid))

                # Grab first file as we will associate the FeatureAsset with just one file
                first_file = point_cloud.files_info[0] if point_cloud.files_info else {}
                original_system = first_file.get("original_system")
                original_path = first_file.get("original_path")

                fa = FeatureAsset(
                    uuid=asset_uuid,
                    asset_type="point_cloud",
                    path=get_asset_relative_path(asset_path),
                    display_path=point_cloud.description,
                    feature=feature,
                    original_system=original_system,
                    original_path=original_path,
                    current_system=original_system,
                    current_path=original_path,
                )
                feature.assets.append(fa)
                point_cloud.feature = feature

            feature.the_geom = from_shape(convert_3D_2D(outline), srid=4326)
            point_cloud.task.status = TaskStatus.COMPLETED
            point_cloud.task.description = ""

            point_cloud_asset_path = get_asset_path(feature.assets[0].path)
            session.add(point_cloud)
            session.add(feature)
            session.commit()

            shutil.rmtree(point_cloud_asset_path, ignore_errors=True)
            shutil.move(path_temp_processed_point_cloud_path, point_cloud_asset_path)


def _update_point_cloud_task(
    database_session, pointCloudId: int, description: str = None, status: str = None
):
    task = PointCloudService.get(database_session, pointCloudId).task
    if description is not None:
        task.description = description
    if status is not None:
        task.status = status
    database_session.add(task)
    database_session.commit()


def _handle_point_cloud_conversion_error(
    pointCloudId, userId, files, error_description
):
    with create_task_session() as session:
        user = session.get(User, userId)
        logger.exception(
            f"point cloud:{pointCloudId} conversion failed for user:{user.username} and files:{files}. "
            f"error:  {error_description}"
        )
        _update_point_cloud_task(
            session,
            pointCloudId,
            description=error_description,
            status=TaskStatus.FAILED,
        )
        send_progress_update(
            user,
            celery.current_task.request.id,
            "error",
            f"Processing failed for point cloud ({pointCloudId})!",
        )


@app.task(queue="heavy")
def import_point_clouds_from_tapis(userId: int, files, pointCloudId: int):
    """
    Imports additional point cloud files from Tapis into an existing
    point cloud record. Each file is fetched, validated, and saved before
    triggering Potree conversion. Progress and errors are reflected in the
    associated Task and sent to the user. Typically used for a single
    LAZ file per point cloud, but supports multiple files when needed.
    """
    with create_task_session() as session:
        user = session.get(User, userId)
        client = TapisUtils(session, user)

        point_cloud = PointCloudService.get(session, pointCloudId)
        celery_task_id = celery.uuid()

        logger.info(
            f"point cloud:{pointCloudId} conversion started for user:{user.username} and files:{files}"
        )

        # this initial geoapi.model.Task setup should probably be moved out of the celery task and performed
        # in the request processing (i.e. in ProjectPointCloudsFileImportResource) so that a task can be returned in the
        # request. See https://jira.tacc.utexas.edu/browse/WG-85
        task = Task()
        task.process_id = celery_task_id
        task.status = TaskStatus.RUNNING

        point_cloud.task = task
        session.add(point_cloud)
        session.add(task)
        session.commit()

        new_asset_files = []
        failed_message = None
        for file in files:
            _update_point_cloud_task(
                session,
                pointCloudId,
                description="Importing file ({}/{})".format(
                    len(new_asset_files) + 1, len(files)
                ),
            )

            send_progress_update(user, celery_task_id, "success", task.description)

            system_id = file["system"]
            path = file["path"]

            try:
                tmp_file = client.getFile(system_id, path)
                tmp_file.filename = pathlib.Path(path).name
                file_path = PointCloudService.putPointCloudInOriginalsFileDir(
                    point_cloud.path, tmp_file, tmp_file.filename
                )
                tmp_file.close()

                # save file path as we might need to delete it if there is a problem
                new_asset_files.append(file_path)

                # check if file is okay
                check_point_cloud(file_path)

            except InvalidCoordinateReferenceSystem:
                logger.error(
                    f"Could not import point cloud file ( point cloud: {pointCloudId} , "
                    f"for user:{user.username} due to missing coordinate reference system: {system_id}:{path}"
                )
                failed_message = (
                    "Error importing {}: missing coordinate reference system".format(
                        path
                    )
                )
            except Exception as e:
                logger.exception(
                    f"Could not import point cloud file for user:{user.username} point cloud: {pointCloudId}"
                    f"from tapis: {system_id}/{path} : {e}"
                )
                failed_message = "Unknown error importing {}:{}".format(system_id, path)

            if failed_message:
                for file_path in new_asset_files:
                    logger.info("removing {}".format(file_path))
                    os.remove(file_path)
                _update_point_cloud_task(
                    session,
                    pointCloudId,
                    description=failed_message,
                    status=TaskStatus.FAILED,
                )
                send_progress_update(user, celery_task_id, "error", failed_message)
                return

        # add to our files_info with these new files
        point_cloud.files_info = (point_cloud.files_info or []) + get_point_cloud_info(
            files
        )

        session.add(point_cloud)
        session.commit()

        _update_point_cloud_task(
            session,
            pointCloudId,
            description="Running potree converter",
            status=TaskStatus.RUNNING,
        )
        send_progress_update(
            user,
            celery_task_id,
            "success",
            "Running potree converter (for point cloud {})".format(pointCloudId),
        )
    try:
        # use potree converter to convert las to web-friendly format
        # this operation is memory-intensive and time-consuming.
        convert_to_potree(pointCloudId)
        with create_task_session() as session:
            user = session.get(User, userId)
            logger.info(
                f"point cloud:{pointCloudId} conversion completed for user:{user.username} and files:{files}"
            )
            send_progress_update(
                user,
                celery_task_id,
                "success",
                "Completed potree converter (for point cloud {}).".format(pointCloudId),
            )
    except PointCloudConversionException as e:
        error_description = e.message
        _handle_point_cloud_conversion_error(
            pointCloudId, userId, files, error_description
        )
    except Exception:
        error_description = "Unknown error occurred"
        _handle_point_cloud_conversion_error(
            pointCloudId, userId, files, error_description
        )
