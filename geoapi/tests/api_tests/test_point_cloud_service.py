import pytest
import os
from werkzeug.datastructures import FileStorage
from geoapi.services.point_cloud import PointCloudService
from geoapi.services.features import FeaturesService
from geoapi.models import User, Feature, FeatureAsset, PointCloud
from geoapi.tasks.lidar import convert_to_potree
from geoapi.utils.assets import get_project_asset_dir, get_asset_path
from geoapi.celery_app import app

POINT_CLOUD_DATA = {'description': "description", 'conversion_parameters': "--scale 2.0"}


@pytest.fixture(scope="function")
def celery_task_always_eager():
    app.conf.task_always_eager = True
    yield
    app.conf.task_always_eager = False


def test_add_point_cloud(dbsession, projects_fixture):
    u1 = dbsession.query(User).get(1)

    point_cloud = PointCloudService.create(projectId=projects_fixture.id,
                                           data=POINT_CLOUD_DATA,
                                           user=u1)
    assert point_cloud.description == "description"
    assert point_cloud.conversion_parameters == "--scale 2.0"
    assert not point_cloud.feature
    assert point_cloud.project_id == projects_fixture.id
    assert dbsession.query(PointCloud).count() == 1


@pytest.mark.worker
def test_add_point_cloud_file(dbsession, projects_fixture, point_cloud_fixture,
                              lidar_las1pt2_file_fixture, convert_to_potree_mock):
    task = PointCloudService.fromFileObj(point_cloud_fixture.id, FileStorage(lidar_las1pt2_file_fixture), {})

    assert task.status == "RUNNING"
    assert point_cloud_fixture.task_id == task.id
    # load updated point cloud
    point_cloud = dbsession.query(PointCloud).get(1)
    las_files = os.listdir(get_asset_path(point_cloud.path, PointCloudService.ORIGINAL_FILES_DIR))
    assert len(las_files) == 1
    assert las_files[0] == os.path.basename(lidar_las1pt2_file_fixture.name)

    # run conversion tool (that we had mocked)
    _, convert_kwargs = convert_to_potree_mock.apply_async.call_args
    assert projects_fixture.id == convert_kwargs['args'][0]
    convert_to_potree(projects_fixture.id)

    # load updated point cloud
    point_cloud = dbsession.query(PointCloud).get(1)

    assert point_cloud.task.status == "FINISHED"
    assert dbsession.query(Feature).count() == 1
    assert dbsession.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(point_cloud.project_id))) == 2
    assert len(os.listdir(get_asset_path(point_cloud.feature.assets[0].path))) == 3  # index.html, pointclouds, libs


def test_delete_point_cloud(dbsession, projects_fixture):
    u1 = dbsession.query(User).get(1)

    point_cloud = PointCloudService.create(projectId=projects_fixture.id,
                                           data=POINT_CLOUD_DATA,
                                           user=u1)
    PointCloudService.delete(pointCloudId=point_cloud.id)
    assert dbsession.query(PointCloud).count() == 0
    assert dbsession.query(Feature).count() == 0
    assert len(os.listdir(get_project_asset_dir(point_cloud.project_id))) == 0


@pytest.mark.worker
def test_delete_point_cloud_feature(celery_task_always_eager, dbsession, projects_fixture, point_cloud_fixture,
                                    lidar_las1pt2_file_fixture):
    PointCloudService.fromFileObj(point_cloud_fixture.id, FileStorage(lidar_las1pt2_file_fixture), {})
    point_cloud = dbsession.query(PointCloud).get(1)
    feature_asset_path = get_asset_path(point_cloud.feature.assets[0].path)

    FeaturesService.delete(point_cloud.feature.id)
    assert dbsession.query(PointCloud).count() == 1
    assert dbsession.query(PointCloud).get(1).feature is None
    assert dbsession.query(Feature).count() == 0
    assert dbsession.query(FeatureAsset).count() == 0
    assert os.path.exists(get_asset_path(point_cloud.path, PointCloudService.ORIGINAL_FILES_DIR))
    assert not os.path.exists(feature_asset_path)


def test_update_point_cloud(projects_fixture, point_cloud_fixture, convert_to_potree_mock):
    data = {'description': "new description", 'conversion_parameters': "--scale 5.0"}
    point_cloud = PointCloudService.update(point_cloud_fixture.id, data=data)
    convert_to_potree_mock.apply_async.assert_called_once()
    assert point_cloud.description == "new description"
    assert point_cloud.conversion_parameters == "--scale 5.0"


def test_update_point_cloud_without_changing_conversion_parameters(projects_fixture, point_cloud_fixture,
                                                                   convert_to_potree_mock):
    data = {'description': "new description"}
    point_cloud = PointCloudService.update(point_cloud_fixture.id, data=data)
    convert_to_potree_mock.apply_async.assert_not_called()
    assert point_cloud.description == "new description"