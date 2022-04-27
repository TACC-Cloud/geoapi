import os
import pathlib
import shutil
import uuid
import json
from typing import List, IO

from geoapi.celery_app import app
from celery import uuid as celery_uuid

from geoapi.exceptions import ApiException, InvalidCoordinateReferenceSystem

from geoapi.models import PointCloud, Project, User, Task
from geoapi.db import db_session
from geoapi.log import logging
from geoapi.tasks.lidar import convert_to_potree, check_point_cloud, get_point_cloud_info
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
        Update a PointCloud
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
    def check_file_extension(file_name):
        """ Checks file extension

        :param filename:
        :raises: ApiException
        """
        file_ext = pathlib.Path(file_name).suffix.lstrip('.').lower()
        if file_ext not in PointCloudService.LIDAR_FILE_EXTENSIONS:
            raise ApiException("Invalid file type for point clouds.")


    @staticmethod
    def putPointCloudInOriginalsFileDir(point_cloud_path: str, fileObj: IO, fileName: str):
        """ Put file object in original files directory

        :param point_cloud_path: str
        :param fileObj: IO
        :param fileName: str
        :return: path to point cloud
        """
        file_path = get_asset_path(point_cloud_path,
                                   PointCloudService.ORIGINAL_FILES_DIR,
                                   os.path.basename(fileName))

        with open(file_path, "wb") as f:
            # set current file position to start so all contents are copied.
            fileObj.seek(0)
            shutil.copyfileobj(fileObj, f)
        return file_path


    @staticmethod
    def fromFileObj(pointCloudId: int, fileObj: IO, fileName: str):
        """
        Add a point cloud file

        When point cloud file has been processed, a feature will be created/updated with feature
        asset containing processed point cloud

        Different processing steps are applied asynchronously by default.

        :param pointCloudId: int
        :param fileObj: IO
        :param fileName: str
        :return: processingTask: Task
        """
        PointCloudService.check_file_extension(fileName)

        point_cloud = PointCloudService.get(pointCloudId)

        file_path = PointCloudService.putPointCloudInOriginalsFileDir(point_cloud.path, fileObj, fileName)

        try:
            result = check_point_cloud.apply_async(args=[file_path])
            result.get()
        except InvalidCoordinateReferenceSystem as e:
            os.remove(file_path)
            logger.error("Point cloud file ({}) missing required coordinate reference system".format(file_path))
            raise e

        result = get_point_cloud_info.apply_async(args=[pointCloudId])
        point_cloud.files_info = json.dumps(result.get())

        db_session.add(point_cloud)
        db_session.commit()

        return PointCloudService._process_point_clouds(pointCloudId)

    @staticmethod
    def _process_point_clouds(pointCloudId: int) -> Task:
        """
        Process point cloud files

        :param pointCloudId: int
        :return: processingTask: Task
        """
        point_cloud = PointCloudService.get(pointCloudId)

        celery_task_id = celery_uuid()
        task = Task()
        task.process_id = celery_task_id
        task.status = "RUNNING"
        task.description = "Processing point cloud #{}".format(pointCloudId)

        point_cloud.task = task

        db_session.add(task)
        db_session.add(point_cloud)
        db_session.commit()

        logger.info("Starting potree processing task (#{}:  '{}') for point cloud (#{}).".format(
            task.id, celery_task_id, pointCloudId))

        # Process asynchronously lidar file and add a feature asset
        convert_to_potree.apply_async(args=[pointCloudId], task_id=celery_task_id)

        return task
