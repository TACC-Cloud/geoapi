import os
import shutil
from tempfile import NamedTemporaryFile
from types import SimpleNamespace

import pytest

from geoapi.celery_app import app as celery_app
from geoapi.utils.external_apis import TapisUtils

# fixtures/ lives one level up from api_tests/
FIXTURES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")


@pytest.fixture(autouse=True)
def celery_eager():
    """inspect() dispatches ALL inspection to a worker task; run it in-process so the
    route gets a result without a live worker/broker. The worker CI image has the geo
    CLIs on PATH. Autouse: every inspect call here goes through the task."""
    celery_app.conf.task_always_eager = True
    yield
    celery_app.conf.task_always_eager = False


@pytest.fixture(autouse=True)
def mock_tapis(monkeypatch):
    """Serve LOCAL fixtures in place of Tapis. In these tests the request ``path`` IS a
    local fixture path, so the fakes read from it directly."""

    def _tmp_copy(path, max_bytes=None):
        tmp = NamedTemporaryFile(suffix=os.path.splitext(path)[1])
        with open(path, "rb") as src:
            if max_bytes is None:
                shutil.copyfileobj(src, tmp)
            else:
                tmp.write(src.read(max_bytes))
        tmp.seek(0)
        return tmp

    def fake_partial(self, system_id, path, max_bytes):
        return _tmp_copy(path, max_bytes)

    def fake_full(self, system_id, path):
        return _tmp_copy(path)

    def _entry(p):
        is_dir = os.path.isdir(p)
        return SimpleNamespace(
            type="dir" if is_dir else "file",
            path=p,
            size=None if is_dir else (os.path.getsize(p) if os.path.isfile(p) else None),
        )

    def fake_listing(self, system_id, path):
        # Mimic Tapis: list ONE level (immediate children), dirs marked type="dir".
        # list_tapis_entries recurses via nested calls when recursive=True.
        if os.path.isdir(path):
            return [_entry(os.path.join(path, name)) for name in sorted(os.listdir(path))]
        return [_entry(path)]

    monkeypatch.setattr(TapisUtils, "getFilePartial", fake_partial, raising=False)
    monkeypatch.setattr(TapisUtils, "getFile", fake_full)
    monkeypatch.setattr(TapisUtils, "listing", fake_listing)


def fx(*parts: str) -> str:
    return os.path.join(FIXTURES, *parts)


def _inspect(client, jwt, path, system_id="designsafe.storage.default", recursive=True):
    return client.post(
        "/files/inspect",
        headers={"X-Tapis-Token": jwt},
        json={"system_id": system_id, "path": path, "recursive": recursive},
    )


def _one(resp):
    """Assert a 200 whose body is a single-item list, and return that item."""
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and len(body) == 1
    return body[0]


@pytest.mark.worker
def test_inspect_georeferenced_raster(test_client, user1):
    v = _one(_inspect(test_client, user1.jwt, fx("rasters", "rgbsmall.tif")))
    assert v["is_geospatial"] is True
    assert v["kind"] == "raster"
    assert v["crs"] is not None
    assert v["bounds"] is not None
    assert v["path"].endswith("rgbsmall.tif")


@pytest.mark.worker
def test_inspect_vector_geojson(test_client, user1):
    v = _one(_inspect(test_client, user1.jwt, fx("geojson.json")))
    assert v["is_geospatial"] is True
    assert v["kind"] == "vector"


@pytest.mark.worker
def test_inspect_pointcloud_las(test_client, user1):
    v = _one(_inspect(test_client, user1.jwt, fx("lidar_subset_las1pt2.las")))
    assert v["is_geospatial"] is True
    assert v["kind"] == "pointcloud"
    assert v["driver"] == "LAS"


@pytest.mark.worker
def test_inspect_image_without_geolocation_is_not_geospatial(test_client, user1):
    # A JPEG with no EXIF GPS -> not geospatial (falls back to the plain-image verdict).
    v = _one(_inspect(test_client, user1.jwt, fx("image_no_location_data.jpg")))
    assert v["is_geospatial"] is False
    assert v["kind"] is None


@pytest.mark.worker
def test_inspect_geotagged_image_is_geospatial(test_client, user1):
    # A geotagged JPEG -> geospatial "image" (importable to Hazmapper as a point feature).
    v = _one(_inspect(test_client, user1.jwt, fx("image.jpg")))
    assert v["is_geospatial"] is True
    assert v["kind"] == "image"
    assert v["crs"] == "EPSG:4326"
    assert v["bounds"][0] == v["bounds"][2] and v["bounds"][1] == v["bounds"][3]


@pytest.mark.worker
def test_inspect_non_geospatial_file(test_client, user1):
    v = _one(_inspect(test_client, user1.jwt, fx("not_geospatial.txt")))
    assert v["is_geospatial"] is False
    assert v["kind"] is None


@pytest.mark.worker
def test_inspect_directory_recurses(test_client, user1):
    # A directory path expands to a verdict per file (rasters/ holds several + a README).
    resp = _inspect(test_client, user1.jwt, fx("rasters"))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and len(body) >= 2
    assert all(item["path"] for item in body)  # every verdict names its file
    assert any(item["is_geospatial"] and item["kind"] == "raster" for item in body)


@pytest.mark.worker
def test_inspect_missing_file_is_error(test_client, user1):
    # The Tapis fetch raises for a nonexistent file; the task failure surfaces as >= 400.
    resp = _inspect(test_client, user1.jwt, fx("does_not_exist.tif"))
    assert resp.status_code >= 400


def test_inspect_requires_token(test_client_anonymous_session):
    # No GDAL needed: the guard rejects before any inspection runs (not worker-marked).
    resp = test_client_anonymous_session.post(
        "/files/inspect",
        json={"system_id": "sys", "path": "/whatever.tif"},
    )
    assert resp.status_code == 401


def _list(client, jwt, path, system_id="designsafe.storage.default", recursive=True):
    return client.post(
        "/files/list",
        headers={"X-Tapis-Token": jwt},
        json={"system_id": system_id, "path": path, "recursive": recursive},
    )


def test_list_files_directory(test_client, user1):
    resp = _list(test_client, user1.jwt, fx("rasters"))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and len(body) >= 2
    e = body[0]
    assert e["system"] == "designsafe.storage.default"
    assert e["type"] == "file" and e["path"]
    assert e["geospatial"] in ("yes", "no", "maybe")
    assert all(isinstance(x["size"], int) for x in body)  # sizes populated from listing
    # a .tif is an ambiguous "maybe"; the README.md is "no"
    tifs = [x for x in body if x["extension"] == ".tif"]
    assert tifs and all(x["geospatial"] == "maybe" for x in tifs)
    readmes = [x for x in body if x["path"].endswith("README.md")]
    assert readmes and all(x["geospatial"] == "no" for x in readmes)


def test_list_files_shallow_shows_dirs(test_client, user1, tmp_path):
    (tmp_path / "a.tif").write_bytes(b"II*\x00")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.las").write_bytes(b"LASF")
    # recursive=false -> immediate children only: a.tif (file) + sub (dir), NOT sub/b.las
    body = _list(test_client, user1.jwt, str(tmp_path), recursive=False).json()
    by_name = {os.path.basename(e["path"]): e for e in body}
    assert by_name["a.tif"]["type"] == "file"
    assert by_name["sub"]["type"] == "dir"
    assert by_name["sub"]["geospatial"] is None and by_name["sub"]["extension"] is None
    assert not any(e["path"].endswith("b.las") for e in body)


def test_list_files_recursive_descends(test_client, user1, tmp_path):
    (tmp_path / "a.tif").write_bytes(b"II*\x00")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.las").write_bytes(b"LASF")
    # recursive=true -> every file under the tree, no dir entries
    body = _list(test_client, user1.jwt, str(tmp_path), recursive=True).json()
    assert any(e["path"].endswith("b.las") for e in body)
    assert all(e["type"] == "file" for e in body)


def test_list_requires_token(test_client_anonymous_session):
    resp = test_client_anonymous_session.post(
        "/files/list", json={"system_id": "sys", "path": "/whatever"}
    )
    assert resp.status_code == 401


def test_validate_listing_path():
    # Listing My Data's root (the shared storage root of all users) is refused; the caller
    # must target /<username>/... Other systems and non-root paths are fine.
    from geoapi.exceptions import ApiException
    from geoapi.services.file_inspection import validate_listing_path

    for bad in ("/", "", "  "):
        with pytest.raises(ApiException):
            validate_listing_path("designsafe.storage.default", bad)
    # these do NOT raise
    validate_listing_path("designsafe.storage.default", "/bob/data")
    validate_listing_path("some.other.system", "/")


def test_inspect_mydata_root_is_error(test_client, user1):
    # Not worker-marked: inspect() rejects root before dispatching to the worker.
    resp = _inspect(test_client, user1.jwt, "/", system_id="designsafe.storage.default")
    assert resp.status_code == 400


def test_list_mydata_root_is_error(test_client, user1):
    # Not worker-marked: the guard rejects before any listing runs.
    resp = _list(test_client, user1.jwt, "/", system_id="designsafe.storage.default")
    assert resp.status_code == 400
