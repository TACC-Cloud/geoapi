import pytest
import geoapi.utils.features as features_util


def test_is_member_of_rapp_project_folder():
    assert not features_util.is_member_of_rapp_project_folder("/")
    assert not features_util.is_member_of_rapp_project_folder("/foo/")

    assert features_util.is_member_of_rapp_project_folder("/RApp/foo.txt")
    assert features_util.is_member_of_rapp_project_folder("/RApp/bar/foo.txt")


def test_is_member_of_rqa_folder():
    assert not features_util.is_member_of_rqa_folder("/")
    assert not features_util.is_member_of_rqa_folder("/foo/")

    assert features_util.is_member_of_rqa_folder("/RApp/foo.rqa/test.rq")
    assert features_util.is_member_of_rqa_folder("/bar/foo.rqa/test.jpg")


def test_is_file_supported_for_automatic_scraping():
    assert not features_util.is_file_supported_for_automatic_scraping("foo")
    assert not features_util.is_file_supported_for_automatic_scraping("foo.txt")
    assert not features_util.is_file_supported_for_automatic_scraping("foo.gif")
    assert not features_util.is_file_supported_for_automatic_scraping("foo.ini")
    assert not features_util.is_file_supported_for_automatic_scraping("foo.las")
    assert not features_util.is_file_supported_for_automatic_scraping("foo.laz")

    assert features_util.is_file_supported_for_automatic_scraping("foo.jpg")
    assert features_util.is_file_supported_for_automatic_scraping("foo.JPG")
    assert features_util.is_file_supported_for_automatic_scraping("foo.jpeg")
    assert features_util.is_file_supported_for_automatic_scraping("foo.JPEG")

    assert features_util.is_file_supported_for_automatic_scraping("foo.geojson")

    assert features_util.is_file_supported_for_automatic_scraping("foo.mp4")
    assert features_util.is_file_supported_for_automatic_scraping("foo.mov")
    assert features_util.is_file_supported_for_automatic_scraping("foo.mpeg4")
    assert features_util.is_file_supported_for_automatic_scraping("foo.webm")

    assert features_util.is_file_supported_for_automatic_scraping("foo.gpx")

    assert features_util.is_file_supported_for_automatic_scraping("foo.rq")

    assert features_util.is_file_supported_for_automatic_scraping("foo.shp")

def test_is_supported_for_automatic_scraping_without_metadata():
    assert not features_util.is_supported_for_automatic_scraping_without_metadata("foo")
    assert not features_util.is_supported_for_automatic_scraping_without_metadata("foo.txt")
    assert not features_util.is_supported_for_automatic_scraping_without_metadata("foo.gif")
    assert not features_util.is_supported_for_automatic_scraping_without_metadata("foo.ini")
    assert not features_util.is_supported_for_automatic_scraping_without_metadata("foo.las")
    assert not features_util.is_supported_for_automatic_scraping_without_metadata("foo.laz")
    assert not features_util.is_supported_for_automatic_scraping_without_metadata("foo.mp4")

    assert features_util.is_supported_for_automatic_scraping_without_metadata("foo.jpg")
    assert features_util.is_supported_for_automatic_scraping_without_metadata("foo.JPG")
    assert features_util.is_supported_for_automatic_scraping_without_metadata("foo.jpeg")
    assert features_util.is_supported_for_automatic_scraping_without_metadata("foo.JPEG")

    assert features_util.is_supported_for_automatic_scraping_without_metadata("foo.geojson")

    assert features_util.is_supported_for_automatic_scraping_without_metadata("foo.gpx")

    assert features_util.is_supported_for_automatic_scraping_without_metadata("foo.rq")

    assert features_util.is_supported_for_automatic_scraping_without_metadata("foo.shp")


def test_is_supported_file_type_in_rapp_folder_and_needs_metadata():
    # not supported type
    assert not features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo")
    assert not features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.txt")
    assert not features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.gif")
    assert not features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.ini")
    assert not features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.las")
    assert not features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.laz")
    assert not features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.geojson")
    assert not features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.rq")
    assert not features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.gpx")
    assert not features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.shp")

    # not in Rapp folder
    assert not features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/bar/foo.jpg")

    assert features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.jpg")
    assert features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.JPG")
    assert features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.jpeg")
    assert features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.JPEG")

    assert features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.mp4")
    assert features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.mov")
    assert features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.mpeg4")
    assert features_util.is_supported_file_type_in_rapp_folder_and_needs_metadata("/RApp/foo.webm")
