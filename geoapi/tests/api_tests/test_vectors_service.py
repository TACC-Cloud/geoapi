from geoapi.services.vectors import VectorService
import fiona
import pytest


def test_process_shapefile(shapefile_fixture, shapefile_additional_files_fixture, shapefile_first_element_geometry):
    geom, properties = next(VectorService.process_shapefile(shapefile_fixture,
                                                            additional_files=shapefile_additional_files_fixture))

    assert geom.wkt == shapefile_first_element_geometry
    assert properties == {'continent': 'South America', 'gdp_md_est': 436100.0, 'iso_a3': 'CHL',
                          'name': 'Chile', 'pop_est': 17789267}


def test_process_shapefile_missing_additional_files(shapefile_fixture):
    with pytest.raises(fiona.errors.DriverError):
        _, _ = next(VectorService.process_shapefile(shapefile_fixture, additional_files=[]))
