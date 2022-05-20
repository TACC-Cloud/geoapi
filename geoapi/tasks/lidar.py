import os
import uuid
import subprocess
import pathlib
import re
import shutil
import celery
from geoalchemy2.shape import from_shape

from geoapi.log import logging
from geoapi.utils.lidar import getProj4, get_bounding_box_2d
from geoapi.utils import geometries
from geoapi.celery_app import app
from geoapi.db import db_session
from geoapi.models import Task
from geoapi.utils.assets import make_project_asset_dir, get_asset_path, get_asset_relative_path

logger = logging.getLogger(__file__)


def get_point_cloud_files(path):
    """
    Get all point cloud files in a path
    :param path: strings
    :return: list of file paths of point cloud files
    """
    from geoapi.services.point_cloud import PointCloudService
    input_files = [get_asset_path(path, file) for file in os.listdir(path)
                   if pathlib.Path(file).suffix.lstrip('.').lower() in PointCloudService.LIDAR_FILE_EXTENSIONS]
    return input_files


@app.task()
def check_point_cloud(file_path: str) -> None:
    """
    Check point cloud file that it has required info
    :param file_path: str
    :return: None
    :raises InvalidCoordinateReferenceSystem: if file missing crs
    """
    # TODO make this a check about if we have enough info ect.
    getProj4(file_path)


@app.task()
def get_point_cloud_info(pointCloudId: int) -> dict:
    """
    Get info on las files
    :param pointCloudId: int
    :return: None
    """
    from geoapi.services.point_cloud import PointCloudService

    point_cloud = PointCloudService.get(pointCloudId)
    path_to_original_point_clouds = get_asset_path(point_cloud.path, PointCloudService.ORIGINAL_FILES_DIR)
    input_files = get_point_cloud_files(path_to_original_point_clouds)

    return [{'name': os.path.basename(f)} for f in input_files]


class PointCloudProcessingTask(celery.Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.info("Task ({}, point cloud {}) failed: {}".format(task_id, args, exc))
        failed_task = db_session.query(Task).filter(Task.process_id == task_id).first()
        failed_task.status = "FAILED"
        failed_task.description = ""
        db_session.add(failed_task)
        db_session.commit()


@app.task(bind=True, base=PointCloudProcessingTask)
def convert_to_potree(self, pointCloudId: int) -> None:
    """
    Use the potree converter to convert a LAS/LAZ file to potree format
    :param pointCloudId: int
    :return: None
    """
    from geoapi.models import Feature, FeatureAsset
    from geoapi.services.point_cloud import PointCloudService

    point_cloud = PointCloudService.get(pointCloudId)

    path_to_original_point_clouds = get_asset_path(point_cloud.path, PointCloudService.ORIGINAL_FILES_DIR)
    path_temp_processed_point_cloud_path = get_asset_path(point_cloud.path, PointCloudService.PROCESSED_DIR)

    input_files = [get_asset_path(path_to_original_point_clouds, file)
                   for file in os.listdir(path_to_original_point_clouds)
                   if pathlib.Path(file).suffix.lstrip('.').lower() in PointCloudService.LIDAR_FILE_EXTENSIONS]

    outline = get_bounding_box_2d(input_files)

    command = [
        "PotreeConverter",
        "--verbose",
        "-i",
        path_to_original_point_clouds,
        "-o",
        path_temp_processed_point_cloud_path,
        "--overwrite",
        "--generate-page",
        "index"
    ]
    if point_cloud.conversion_parameters:
        command.extend(point_cloud.conversion_parameters.split())
    logger.info("Processing point cloud (#{}):  {}".format(pointCloudId, " ".join(command)))
    subprocess.run(command, check=True, capture_output=True, text=True)

    # Create preview viewer html (with no menu and now nsf logo)
    with open(os.path.join(path_temp_processed_point_cloud_path, "preview.html"), 'w+') as preview:
        with open(os.path.join(path_temp_processed_point_cloud_path, "index.html"), 'r') as viewer:
            content = viewer.read()
            content = re.sub(r"<div class=\"nsf_logo\"(.+?)</div>", '', content, flags=re.DOTALL)
            content = content.replace("viewer.toggleSidebar()", "$('.potree_menu_toggle').hide()")
            preview.write(content)

    if point_cloud.feature_id:
        feature = point_cloud.feature
    else:
        feature = Feature()
        feature.project_id = point_cloud.project_id

        asset_uuid = uuid.uuid4()
        base_filepath = make_project_asset_dir(point_cloud.project_id)
        asset_path = os.path.join(base_filepath, str(asset_uuid))
        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="point_cloud",
            path=get_asset_relative_path(asset_path),
            display_path=point_cloud.description,
            feature=feature
        )
        feature.assets.append(fa)
        point_cloud.feature = feature

    feature.the_geom = from_shape(geometries.convert_3D_2D(outline), srid=4326)
    point_cloud.task.status = "FINISHED"
    point_cloud.task.description = ""

    point_cloud_asset_path = get_asset_path(feature.assets[0].path)
    shutil.rmtree(point_cloud_asset_path, ignore_errors=True)
    shutil.move(path_temp_processed_point_cloud_path, point_cloud_asset_path)

    try:
        db_session.add(point_cloud)
        db_session.add(feature)
        db_session.commit()
    except:  # noqa: E722
        db_session.rollback()
        raise
