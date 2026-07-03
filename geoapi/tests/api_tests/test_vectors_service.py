import os
import shutil

import geopandas as gpd
from shapely.geometry import Point

from geoapi.services.vectors import VectorService, SUPPORTED_VECTOR_EXTENSIONS
import pyogrio
import pytest


def test_supported_vector_extensions():
    assert {"geojson", "shp", "gpx", "gpkg", "parquet", "geoparquet"}.issubset(
        SUPPORTED_VECTOR_EXTENSIONS
    )


@pytest.mark.worker
def test_convert_to_geojson_shapefile(
    shapefile_fixture, shapefile_additional_files_fixture
):
    geojson_path, bbox = VectorService.convert_to_geojson(
        shapefile_fixture, additional_files=shapefile_additional_files_fixture
    )
    try:
        # a GeoJSON file was written to a real temp directory
        assert os.path.isfile(geojson_path)

        # bbox is a valid lon/lat extent
        assert set(bbox) == {"minx", "miny", "maxx", "maxy"}
        assert bbox["minx"] < bbox["maxx"]
        assert bbox["miny"] < bbox["maxy"]
        # within lon/lat range, allowing tiny FP slop at the antimeridian/poles
        assert -180.01 <= bbox["minx"] and bbox["maxx"] <= 180.01
        assert -90.01 <= bbox["miny"] and bbox["maxy"] <= 90.01

        # output is EPSG:4326 and 2D
        gdf = gpd.read_file(geojson_path)
        assert gdf.crs.to_epsg() == 4326
        assert not gdf.geometry.iloc[0].has_z
    finally:
        shutil.rmtree(os.path.dirname(geojson_path), ignore_errors=True)


@pytest.mark.worker
def test_convert_to_geojson_missing_shapefile_additional_files(shapefile_fixture):
    # a shapefile cannot be read without its companion files (.shx/.dbf/...)
    with pytest.raises(pyogrio.errors.DataSourceError):
        VectorService.convert_to_geojson(shapefile_fixture, additional_files=[])


@pytest.mark.worker
def test_force_2d_strips_z():
    gdf = gpd.GeoDataFrame(geometry=[Point(1.0, 2.0, 3.0)], crs="EPSG:4326")
    assert gdf.geometry.iloc[0].has_z

    result = VectorService._force_2d(gdf)
    assert not result.geometry.iloc[0].has_z
