import os
import pathlib
import shutil
import uuid
from typing import List, IO

from celery import uuid as celery_uuid

from geoapi.exceptions import ApiException

from geoapi.models import PointCloud, Project, User, Task
from geoapi.log import logging
from geoapi.tasks.lidar import convert_to_potree
from geoapi.utils.assets import (
    make_project_asset_dir,
    delete_assets,
    get_asset_relative_path,
    get_asset_path,
)

logger = logging.getLogger(__name__)


class PointCloudService:
    LIDAR_FILE_EXTENSIONS = ("las", "laz")
    ORIGINAL_FILES_DIR = "original_files"

    PROCESSED_DIR = "point_cloud"

    @staticmethod
    def get(database_session, pointCloudId: int) -> PointCloud:
        """
        Retrieve a single PointCloud
        :param pointCloudId: int
        :return: PointCloud
        """
        point_cloud = database_session.get(PointCloud, pointCloudId)
        return point_cloud

    @staticmethod
    def list(database_session, projectId: int) -> List[PointCloud]:
        """
        Retrieve all point clouds
        :param projectId: int
        :return: list[PointCloud]
        """
        project = database_session.get(Project, projectId)
        return project.point_clouds

    @staticmethod
    def create(database_session, projectId: int, data: dict, user: User) -> PointCloud:
        """
        Create a PointCloud for a user.
        :param projectId: int
        :param data: dict
        :param user: User
        :return: PointCloud
        """

        point_cloud_uid = uuid.uuid4()
        point_cloud_path = os.path.join(
            make_project_asset_dir(projectId), str(point_cloud_uid)
        )
        file_point_cloud_path = os.path.join(
            point_cloud_path, PointCloudService.ORIGINAL_FILES_DIR
        )
        pathlib.Path(file_point_cloud_path).mkdir(parents=True, exist_ok=True)

        point_cloud = PointCloud(**data)
        point_cloud.project_id = projectId
        point_cloud.tenant_id = user.tenant_id
        point_cloud.uuid = point_cloud_uid
        point_cloud.path = get_asset_relative_path(point_cloud_path)

        database_session.add(point_cloud)
        database_session.commit()
        return point_cloud

    @staticmethod
    def update(database_session, pointCloudId: int, data: dict) -> PointCloud:
        """
        Update a PointCloud
        :param pointCloudId: int
        :param data: dict
        :return: Project
        """
        point_cloud = PointCloudService.get(database_session, pointCloudId)

        previous_conversion_parameters = point_cloud.conversion_parameters
        for key, value in data.items():
            setattr(point_cloud, key, value)
        database_session.commit()

        if (
            "conversion_parameters" in data
            and previous_conversion_parameters != data["conversion_parameters"]
        ):
            PointCloudService._process_point_clouds(database_session, pointCloudId)

        return point_cloud

    @staticmethod
    def delete(database_session, pointCloudId: int) -> None:
        """
        Delete a PointCloud
        :param pointCloudId: int
        :return: None
        """
        point_cloud = PointCloudService.get(database_session, pointCloudId)
        delete_assets(projectId=point_cloud.project_id, uuid=point_cloud.uuid)
        database_session.delete(point_cloud)
        database_session.commit()

    @staticmethod
    def check_file_extension(file_name):
        """Checks file extension

        :param filename:
        :raises: ApiException
        """
        file_ext = pathlib.Path(file_name).suffix.lstrip(".").lower()
        if file_ext not in PointCloudService.LIDAR_FILE_EXTENSIONS:
            raise ApiException("Invalid file type for point clouds.")

    @staticmethod
    def putPointCloudInOriginalsFileDir(
        point_cloud_path: str, fileObj: IO, fileName: str
    ):
        """Put file object in original files directory

        :param point_cloud_path: str
        :param fileObj: IO
        :param fileName: str
        :return: path to point cloud
        """
        file_path = get_asset_path(
            point_cloud_path,
            PointCloudService.ORIGINAL_FILES_DIR,
            os.path.basename(fileName),
        )

        with open(file_path, "wb") as f:
            # set current file position to start so all contents are copied.
            fileObj.seek(0)
            shutil.copyfileobj(fileObj, f)
        return file_path

    @staticmethod
    def _process_point_clouds(database_session, pointCloudId: int) -> Task:
        """
        Process point cloud files

        :param pointCloudId: int
        :return: processingTask: Task
        """
        point_cloud = PointCloudService.get(database_session, pointCloudId)

        celery_task_id = celery_uuid()
        task = Task()
        task.process_id = celery_task_id
        task.status = "RUNNING"
        task.description = "Processing point cloud #{}".format(pointCloudId)

        point_cloud.task = task

        database_session.add(task)
        database_session.add(point_cloud)
        database_session.commit()

        logger.info(
            "Starting potree processing task (#{}:  '{}') for point cloud (#{}).".format(
                task.id, celery_task_id, pointCloudId
            )
        )

        # Process asynchronously lidar file and add a feature asset
        convert_to_potree.apply_async(args=[pointCloudId], task_id=celery_task_id)

        return task
