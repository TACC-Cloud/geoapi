import os
import uuid
import subprocess
import pathlib
import shutil
from geoalchemy2.shape import from_shape

from geoapi.utils.lidar import Lidar
from geoapi.celery_app import app
from geoapi.db import db_session


@app.task(bind=True)
def convert_to_potree(self, pointCloudId: int) -> None:
    """
    Use the potree converter to convert a LAS/LAZ file to potree format
    :param pointCloudId: int
    :return: None
    """
    from geoapi.models import Feature, FeatureAsset, Task
    from geoapi.services.point_cloud import PointCloudService

    point_cloud = PointCloudService.get(pointCloudId)

    point_cloud_path = os.path.join(point_cloud.path, PointCloudService.ORIGINAL_FILES_DIR)
    processed_point_cloud_path = os.path.join(point_cloud.path, PointCloudService.PROCESSED_DIR)
    processed_point_cloud_path_temp = os.path.join(point_cloud.path, PointCloudService.PROCESSED_DIR + "temp")

    input_files = [os.path.join(point_cloud_path, file) for file in os.listdir(point_cloud_path)
                   if pathlib.Path(file).suffix.lstrip('.') in PointCloudService.LIDAR_FILE_EXTENSIONS]
    outline = Lidar.getBoundingBox(input_files)

    # todo put this in a try block and update task + return if problem here plus update associated Task
    # todo add potree params (point_cloud.conversion_parameters)
    subprocess.run([
        "PotreeConverter",
        "-i",
        point_cloud_path,
        "-o",
        processed_point_cloud_path_temp,
        "--overwrite",
        "--generate-page",
        "index"
    ])

    if point_cloud.feature_id:
        feature = point_cloud.feature
    else:
        feature = Feature()
        feature.project_id = point_cloud.project_id

        # TODO metadata for feature
        # feature.properties = metadata

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
