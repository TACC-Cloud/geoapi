import pytest
import os
from werkzeug.datastructures import FileStorage

from geoapi.services.point_cloud import PointCloudService
from geoapi.models import User, Feature, FeatureAsset, PointCloud
from geoapi.tasks.lidar import convert_to_potree


POINT_CLOUD_DATA = {'description': "description", 'conversion_parameters': "--something"}

def test_add_point_cloud(dbsession, projects_fixture):
    u1 = dbsession.query(User).get(1)

    point_cloud = PointCloudService.create(projectId=projects_fixture.id,
                                           data=POINT_CLOUD_DATA,
                                           user=u1)
    assert point_cloud.description == "description"
    assert point_cloud.conversion_parameters == "--something"
    assert not point_cloud.feature
    assert point_cloud.project_id == projects_fixture.id
    assert dbsession.query(PointCloud).count() == 1

@pytest.mark.worker
def test_add_point_cloud_file(dbsession, projects_fixture, point_cloud_fixture, lidar_las1pt2_file_fixture, convert_to_potree_mock):
    task = PointCloudService.fromFileObj(point_cloud_fixture.id, FileStorage(lidar_las1pt2_file_fixture), {})

    assert task.status == "RUNNING"
    assert point_cloud_fixture.task_id == task.id

    # load updated point cloud
    point_cloud = dbsession.query(PointCloud).get(1)
    las_files = os.listdir(os.path.join(point_cloud.path,
                                       PointCloudService.ORIGINAL_FILES_DIR))
    assert len(las_files) == 1
    assert las_files[0] == os.path.basename(lidar_las1pt2_file_fixture.name)

    # run conversion tool (that we had mocked)
    _, convert_kwargs  = convert_to_potree_mock.apply_async.call_args
    assert projects_fixture.id == convert_kwargs['args'][0]
    convert_to_potree(projects_fixture.id)

    # load updated point cloud
    point_cloud = dbsession.query(PointCloud).get(1)

    assert point_cloud.task.status == "FINISHED"
    assert dbsession.query(Feature).count() == 1
    assert dbsession.query(FeatureAsset).count() == 1
    assert os.path.exists(os.path.join(point_cloud.path, PointCloudService.PROCESSED_DIR))