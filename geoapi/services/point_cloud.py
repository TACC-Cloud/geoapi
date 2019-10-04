import os
import pathlib
import uuid
from typing import List, IO, Dict

from celery.task.control import revoke
from celery import uuid as celery_uuid

from geoapi.exceptions import ApiException

from geoapi.models import PointCloud, Project, User, Task
from geoapi.db import db_session
from geoapi.log import logging
from geoapi.tasks.lidar import convert_to_potree
from geoapi.utils.assets import make_project_asset_dir, delete_assets, get_asset_relative_path, get_asset_path

logger = logging.getLogger(__name__)


class PointCloudService:
    LIDAR_FILE_EXTENSIONS = (
        'las', 'laz'
    )
    ORIGINAL_FILES_DIR = "original_files"

    PROCESSED_DIR = "point_cloud"

    @staticmethod
    def get(pointCloudId: int) -> PointCloud:
        """
        Retrieve a single PointCloud
        :param pointCloudId: int
        :return: PointCloud
        """
        point_cloud = db_session.query(PointCloud).get(pointCloudId)
        return point_cloud

    @staticmethod
    def list(projectId: int) -> List[PointCloud]:
        """
        Retrieve all point clouds
        :param projectId: int
        :return: list[PointCloud]
        """
        project = db_session.query(Project).get(projectId)
        return project.point_clouds

    @staticmethod
    def create(projectId: int, data: dict, user: User) -> PointCloud:
        """
        Create a PointCloud for a user.
        :param projectId: int
        :param data: dict
        :param user: User
        :return: PointCloud
        """

        point_cloud_uid = uuid.uuid4()
        point_cloud_path = os.path.join(make_project_asset_dir(projectId), str(point_cloud_uid))
        file_point_cloud_path = os.path.join(point_cloud_path, PointCloudService.ORIGINAL_FILES_DIR)
        pathlib.Path(file_point_cloud_path).mkdir(parents=True, exist_ok=True)

        point_cloud = PointCloud(**data)
        point_cloud.project_id = projectId
        point_cloud.tenant_id = user.tenant_id
        point_cloud.uuid = point_cloud_uid
        point_cloud.path = get_asset_relative_path(point_cloud_path)

        db_session.add(point_cloud)
        db_session.commit()
        return point_cloud

    @staticmethod
    def update(pointCloudId: int, data: dict) -> PointCloud:
        """
        Delete a PointCloud
        :param pointCloudId: int
        :param data: dict
        :return: Project
        """
        point_cloud = PointCloudService.get(pointCloudId)

        previous_conversion_parameters = point_cloud.conversion_parameters
        for key, value in data.items():
            setattr(point_cloud, key, value)
        db_session.commit()

        if 'conversion_parameters' in data and previous_conversion_parameters != data['conversion_parameters']:
            PointCloudService._process_point_clouds(pointCloudId)

        return point_cloud

    @staticmethod
    def delete(pointCloudId: int) -> None:
        """
        Delete a PointCloud
        :param pointCloudId: int
        :return: None
        """
        point_cloud = PointCloudService.get(pointCloudId)
        delete_assets(projectId=point_cloud.project_id, uuid=point_cloud.uuid)
        db_session.delete(point_cloud)
        db_session.commit()

    @staticmethod
    def fromFileObj(pointCloudId: int, fileObj: IO, metadata: Dict):
        """
        Add a point cloud file

        When point cloud file has been processed, a feature will be created/updated with feature
        asset containing processed point cloud

        :param pointCloudId: int
        :param fileObj: file
        :return: processingTask: Task
        """
        ext = pathlib.Path(fileObj.filename).suffix.lstrip('.')
        if ext not in PointCloudService.LIDAR_FILE_EXTENSIONS:
            raise ApiException("File type not supported.")

        point_cloud = PointCloudService.get(pointCloudId)
        file_path = get_asset_path(point_cloud.path,
                                   PointCloudService.ORIGINAL_FILES_DIR,
                                   os.path.basename(fileObj.filename))

        with open(file_path, 'wb') as f:
            f.write(fileObj.read())

        return PointCloudService._process_point_clouds(pointCloudId)

    @staticmethod
    def _process_point_clouds(pointCloudId: int):
        """
        Process point cloud files

        :param pointCloudId: int
        :return: processingTask: Task
        """
        # TODO lock point cloud while we cancel previous task and start a new one (e.g. with_for_update)
        point_cloud = PointCloudService.get(pointCloudId)

        if point_cloud.task and point_cloud.task.status != "FINISHED":
            logger.info("Terminating previous unfinished processing task {}.".format(point_cloud.task.process_id))
            revoke(point_cloud.task.process_id, terminate=True)
            point_cloud.task.status = "CANCELED"
            db_session.add(point_cloud.task)
            db_session.commit()

        celery_task_id = celery_uuid()
        task = Task()
        task.status = "RUNNING"
        task.process_id = celery_task_id
        task.description = "Processing point cloud #{}".format(pointCloudId)

        point_cloud.task = task

        db_session.add(task)
        db_session.add(point_cloud)
        db_session.commit()

        # Process asynchronously lidar file and add a feature asset
        convert_to_potree.apply_async(args=[pointCloudId], task_id=celery_task_id)
        logger.info("Starting potree processing task (#{}:  '{}') for point cloud (#{}).".format(
            task.id, celery_task_id, pointCloudId))

        return task
