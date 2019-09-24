import os
import uuid
import subprocess
import pathlib
import shutil
import celery
from geoalchemy2.shape import from_shape

from geoapi.log import logging
from geoapi.utils.lidar import Lidar
from geoapi.celery_app import app
from geoapi.db import db_session
from geoapi.models import Task


logger = logging.getLogger(__file__)


class PointCloudProcessingTask(celery.Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.info("Task ({}, point cloud {}) failed: {}".format(task_id, args, exc))
        failed_task = db_session.query(Task).filter(Task.process_id == task_id).first()
        failed_task.status = "FAILED"
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

    point_cloud_path = os.path.join(point_cloud.path, PointCloudService.ORIGINAL_FILES_DIR)
    processed_point_cloud_path = os.path.join(point_cloud.path, PointCloudService.PROCESSED_DIR)
    processed_point_cloud_path_temp = os.path.join(point_cloud.path, PointCloudService.PROCESSED_DIR + "temp")

    input_files = [os.path.join(point_cloud_path, file) for file in os.listdir(point_cloud_path)
                   if pathlib.Path(file).suffix.lstrip('.') in PointCloudService.LIDAR_FILE_EXTENSIONS]
    outline = Lidar.getBoundingBox(input_files)

    command = [
        "PotreeConverter",
        "-i",
        point_cloud_path,
        "-o",
        processed_point_cloud_path_temp,
        "--overwrite",
        "--generate-page",
        "index"
    ]
    command.extend(point_cloud.conversion_parameters.split())
    logger.info("Processing point cloud (#{}):  {}".format(pointCloudId, " ".join(command)))
    subprocess.run(command, check=True, capture_output=True, text=True)

    if point_cloud.feature_id:
        feature = point_cloud.feature
    else:
        feature = Feature()
        feature.project_id = point_cloud.project_id

        asset_uuid = uuid.uuid4()

        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="point_cloud",
            path=processed_point_cloud_path,
            feature=feature
        )
        feature.assets.append(fa)

        point_cloud.feature = feature
        db_session.add(point_cloud)

    feature.the_geom = from_shape(outline, srid=4326)
    point_cloud.task.status = "FINISHED"

    shutil.rmtree(processed_point_cloud_path, ignore_errors=True)
    shutil.move(processed_point_cloud_path_temp, processed_point_cloud_path)

    db_session.add(point_cloud)
    db_session.add(feature)
    db_session.commit()
