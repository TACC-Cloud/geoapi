import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from geoapi.tasks.raster import (
    _validate_raster_name,
    import_tile_servers_from_tapis,
)
from geoapi.models import TileServer, TaskStatus
from geoapi.utils.external_apis import TapisFileGetError
from geoapi.utils.assets import get_project_asset_dir


def test_validate_tif():
    """Test that various .tif extensions are valid"""
    _validate_raster_name("test.tif")
    _validate_raster_name("test.tiff")
    _validate_raster_name("test.geotiff")
    _validate_raster_name("test.TIF")
    _validate_raster_name("test.TIFF")
    _validate_raster_name("test.GeoTiff")


def test_validate_invalid_extension():
    """Test that invalid extensions raise ValueError"""
    with pytest.raises(ValueError, match="Unsupported raster extension"):
        _validate_raster_name("test.jpg")

    with pytest.raises(ValueError, match="Unsupported raster extension"):
        _validate_raster_name("test")

    with pytest.raises(ValueError, match="Unsupported raster extension"):
        _validate_raster_name("test.png")


@pytest.mark.worker
@patch("geoapi.tasks.raster.TapisUtils")
def test_import_tile_server_singleband_success(
    MockTapisUtils,
    user1,
    projects_fixture,
    task_fixture,
    raster_singleband_int16_m30dem,
    db_session,
):
    MockTapisUtils().getFile.return_value = raster_singleband_int16_m30dem

    tapis_file = {"system": "testSystem", "path": "/testPath/raster.tif"}

    import_tile_servers_from_tapis(
        user_id=user1.id,
        tapis_file=tapis_file,
        project_id=projects_fixture.id,
        task_id=task_fixture.id,
    )

    tile_server = db_session.query(TileServer).first()
    assert tile_server is not None
    assert tile_server.project_id == projects_fixture.id
    assert tile_server.name == "/testPath/raster.tif"
    assert tile_server.type == "xyz"
    assert tile_server.kind == "cog"
    assert tile_server.internal is True
    assert tile_server.original_system == "testSystem"
    assert tile_server.original_path == "/testPath/raster.tif"
    assert tile_server.url.startswith(get_project_asset_dir(projects_fixture.id))
    assert tile_server.url.endswith(".cog.tif")

    assert tile_server.tileOptions["minZoom"] == 0
    assert tile_server.tileOptions["maxZoom"] == 12
    assert tile_server.tileOptions["maxNativeZoom"] == 12
    assert tile_server.tileOptions["bounds"] == [
        [
            37.4399741,
            -122.6953125,
        ],
        [
            38.0653924,
            -122.0800781,
        ],
    ]

    assert tile_server.uiOptions["zIndex"] == 0
    assert tile_server.uiOptions["opacity"] == 1
    assert tile_server.uiOptions["isActive"] is True
    assert tile_server.uiOptions["showInput"] is False
    assert tile_server.uiOptions["showDescription"] is False

    # Verify renderOptions for single-band image
    assert "renderOptions" in tile_server.uiOptions
    assert tile_server.uiOptions["renderOptions"]["colormap_name"] == "terrain"

    # Verify task status was updated to COMPLETED
    db_session.refresh(task_fixture)
    assert task_fixture.status == TaskStatus.COMPLETED

    assert tile_server.url.endswith(".cog.tif")
    cog_path = Path(tile_server.url)
    assert cog_path.exists()


@pytest.mark.worker
@patch("geoapi.tasks.raster.TapisUtils")
def test_import_tile_server_rgb_success(
    MockTapisUtils,
    user1,
    projects_fixture,
    task_fixture,
    raster_threeband_byte_rgbsmall,
    db_session,
):
    MockTapisUtils().getFile.return_value = raster_threeband_byte_rgbsmall

    tapis_file = {"system": "testSystem", "path": "/testPath/rgb.tif"}

    import_tile_servers_from_tapis(
        user_id=user1.id,
        tapis_file=tapis_file,
        project_id=projects_fixture.id,
        task_id=task_fixture.id,
    )

    tile_server = db_session.query(TileServer).first()
    assert tile_server is not None

    assert tile_server.uiOptions["zIndex"] == 0
    assert tile_server.uiOptions["opacity"] == 1
    assert tile_server.uiOptions["isActive"] is True
    assert tile_server.uiOptions["showInput"] is False
    assert tile_server.uiOptions["showDescription"] is False

    # Verify renderOptions is empty for multi-band images
    assert tile_server.uiOptions.get("renderOptions", {}) == {}

    db_session.refresh(task_fixture)
    assert task_fixture.status == TaskStatus.COMPLETED


@pytest.mark.worker
@patch("geoapi.tasks.raster.TapisUtils")
def test_import_tile_server_invalid_extension(
    MockTapisUtils,
    user1,
    projects_fixture,
    task_fixture,
    db_session,
):
    """Test that invalid file extensions cause task to fail"""
    tapis_file = {"system": "testSystem", "path": "/testPath/image.jpg"}

    import_tile_servers_from_tapis(
        user_id=user1.id,
        tapis_file=tapis_file,
        project_id=projects_fixture.id,
        task_id=task_fixture.id,
    )

    # Verify no TileServer was created
    assert db_session.query(TileServer).count() == 0

    # Verify task status was updated to FAILED
    db_session.refresh(task_fixture)
    assert task_fixture.status == TaskStatus.FAILED
    assert task_fixture.latest_message.startswith("Invalid file type")

    # Verify TapisUtils.getFile was never called
    MockTapisUtils().getFile.assert_not_called()


@pytest.mark.worker
@patch("geoapi.tasks.raster.TapisUtils")
def test_import_tile_server_tapis_fetch_failure(
    MockTapisUtils,
    user1,
    projects_fixture,
    task_fixture,
    db_session,
):
    """Test handling of Tapis file fetch failures"""
    MockTapisUtils().getFile.side_effect = TapisFileGetError("File not found")

    tapis_file = {"system": "testSystem", "path": "/testPath/raster.tif"}

    import_tile_servers_from_tapis(
        user_id=user1.id,
        tapis_file=tapis_file,
        project_id=projects_fixture.id,
        task_id=task_fixture.id,
    )

    # Verify no TileServer was created
    assert db_session.query(TileServer).count() == 0

    # Verify task status was updated to FAILED
    db_session.refresh(task_fixture)
    assert task_fixture.status == TaskStatus.FAILED
    assert "Failed to get /testPath/raster.tif" == task_fixture.latest_message


@pytest.mark.worker
@patch("geoapi.tasks.raster.gdal_cogify")
@patch("geoapi.tasks.raster.TapisUtils")
def test_import_tile_server_gdal_failure(
    MockTapisUtils,
    mock_gdal_cogify,
    user1,
    projects_fixture,
    task_fixture,
    raster_singleband_int16_m30dem,
    db_session,
):
    """Test handling of GDAL processing failures"""
    MockTapisUtils().getFile.return_value = raster_singleband_int16_m30dem
    mock_gdal_cogify.side_effect = Exception("GDAL processing failed")

    tapis_file = {"system": "testSystem", "path": "/testPath/raster.tif"}

    import_tile_servers_from_tapis(
        user_id=user1.id,
        tapis_file=tapis_file,
        project_id=projects_fixture.id,
        task_id=task_fixture.id,
    )

    # Verify no TileServer was created
    assert db_session.query(TileServer).count() == 0

    # Verify task status was updated to FAILED
    db_session.refresh(task_fixture)
    assert task_fixture.status == TaskStatus.FAILED
    assert "Import failed: /testPath/raster.tif" == task_fixture.latest_message


@pytest.mark.worker
@patch("geoapi.tasks.raster.delete_assets")
@patch("geoapi.tasks.raster.get_cog_metadata")
@patch("geoapi.tasks.raster.TapisUtils")
def test_import_tile_server_metadata_failure_cleanup(
    MockTapisUtils,
    mock_get_cog_metadata,
    mock_delete_assets,
    user1,
    projects_fixture,
    task_fixture,
    raster_singleband_int16_m30dem,
    db_session,
):
    """Test that assets are cleaned up when metadata extraction fails"""
    MockTapisUtils().getFile.return_value = raster_singleband_int16_m30dem
    mock_get_cog_metadata.side_effect = ValueError("Invalid projection")

    tapis_file = {"system": "testSystem", "path": "/testPath/raster.tif"}

    import_tile_servers_from_tapis(
        user_id=user1.id,
        tapis_file=tapis_file,
        project_id=projects_fixture.id,
        task_id=task_fixture.id,
    )

    # Verify cleanup was called
    mock_delete_assets.assert_called_once()
    call_args = mock_delete_assets.call_args
    assert call_args[1]["projectId"] == projects_fixture.id

    # Verify task status was updated to FAILED
    db_session.refresh(task_fixture)
    assert task_fixture.status == TaskStatus.FAILED


@pytest.mark.worker
@patch("geoapi.tasks.raster.TapisUtils")
def test_import_tile_server_temp_file_cleanup(
    MockTapisUtils,
    user1,
    projects_fixture,
    task_fixture,
    raster_singleband_int16_m30dem,
    db_session,
):
    """Test that temporary files are cleaned up after processing"""
    mock_temp_file = MagicMock()
    mock_temp_file.name = raster_singleband_int16_m30dem.name
    MockTapisUtils().getFile.return_value = mock_temp_file

    tapis_file = {"system": "testSystem", "path": "/testPath/raster.tif"}

    import_tile_servers_from_tapis(
        user_id=user1.id,
        tapis_file=tapis_file,
        project_id=projects_fixture.id,
        task_id=task_fixture.id,
    )

    # Verify temp file was closed
    mock_temp_file.close.assert_called_once()
