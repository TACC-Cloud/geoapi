import pytest
import os
from unittest.mock import patch

from geoapi.db import db_session
from geoapi.services.point_cloud import PointCloudService
from geoapi.services.features import FeaturesService
from geoapi.models import User, Feature, FeatureAsset, PointCloud
from geoapi.utils.assets import get_project_asset_dir, get_asset_path
from geoapi.celery_app import app
from geoapi.tasks.external_data import import_point_clouds_from_agave

POINT_CLOUD_DATA = {'description': "description", 'conversion_parameters': "--scale 2.0"}


@pytest.fixture(scope="function")
def celery_task_always_eager():
    app.conf.task_always_eager = True
    yield
    app.conf.task_always_eager = False


def test_add_point_cloud(projects_fixture):
    u1 = db_session.query(User).get(1)

    point_cloud = PointCloudService.create(database_session=db_session,
                                           projectId=projects_fixture.id,
                                           data=POINT_CLOUD_DATA,
                                           user=u1)
    assert point_cloud.description == "description"
    assert point_cloud.conversion_parameters == "--scale 2.0"
    assert not point_cloud.feature
    assert point_cloud.project_id == projects_fixture.id
    assert db_session.query(PointCloud).count() == 1


def test_delete_point_cloud(projects_fixture):
    u1 = db_session.query(User).get(1)

    point_cloud = PointCloudService.create(database_session=db_session,
                                           projectId=projects_fixture.id,
                                           data=POINT_CLOUD_DATA,
                                           user=u1)
    PointCloudService.delete(database_session=db_session, pointCloudId=point_cloud.id)
    assert db_session.query(PointCloud).count() == 0
    assert db_session.query(Feature).count() == 0
    assert len(os.listdir(get_project_asset_dir(point_cloud.project_id))) == 0


@pytest.mark.worker
@patch("geoapi.tasks.external_data.AgaveUtils")
def test_delete_point_cloud_feature(MockAgaveUtils, celery_task_always_eager, projects_fixture, point_cloud_fixture,
                                    lidar_las1pt2_file_fixture):
    # create a point cloud feature so we can delete it
    MockAgaveUtils().getFile.return_value = lidar_las1pt2_file_fixture
    u1 = db_session.query(User).get(1)
    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]
    import_point_clouds_from_agave(u1.id, files, point_cloud_fixture.id)

    db_session.refresh(point_cloud_fixture)

    point_cloud = db_session.query(PointCloud).get(1)
    feature_asset_path = get_asset_path(point_cloud.feature.assets[0].path)

    # delete point cloud feature
    FeaturesService.delete(db_session, point_cloud.feature.id)

    assert db_session.query(PointCloud).count() == 1
    assert db_session.query(PointCloud).get(1).feature is None
    assert db_session.query(Feature).count() == 0
    assert db_session.query(FeatureAsset).count() == 0
    assert os.path.exists(get_asset_path(point_cloud.path, PointCloudService.ORIGINAL_FILES_DIR))
    assert not os.path.exists(feature_asset_path)


def test_update_point_cloud(projects_fixture, point_cloud_fixture, convert_to_potree_mock):
    data = {'description': "new description", 'conversion_parameters': "--scale 5.0"}
    point_cloud = PointCloudService.update(db_session, point_cloud_fixture.id, data=data)
    convert_to_potree_mock.apply_async.assert_called_once()
    assert point_cloud.description == "new description"
    assert point_cloud.conversion_parameters == "--scale 5.0"


def test_update_point_cloud_without_changing_conversion_parameters(projects_fixture, point_cloud_fixture,
                                                                   convert_to_potree_mock):
    data = {'description': "new description"}
    point_cloud = PointCloudService.update(db_session, point_cloud_fixture.id, data=data)
    convert_to_potree_mock.apply_async.assert_not_called()
    assert point_cloud.description == "new description"
