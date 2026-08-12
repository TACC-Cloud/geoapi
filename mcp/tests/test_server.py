"""Unit tests for the MCP server. GeoAPI is mocked with respx -- these tests do NOT
require a running GeoAPI or the geoapi package, and use only mcp/tests/fixtures/.

They cover the acceptance criteria for the MCP layer:
  * a request carrying a Tapis token reaches GeoAPI with that same token,
  * a request without a token fails cleanly,
  * import routes to the correct existing endpoint by file kind (point clouds rejected).
"""

import json
import os

import httpx
import pytest
import respx
from fastmcp.exceptions import ToolError

import server
from conftest import FIXTURES

BASE = server.GEOAPI_BASE_URL


def fx(name: str) -> str:
    """Path to a self-contained fixture (proves mcp tests don't touch geoapi's)."""
    return os.path.join(FIXTURES, name)


# --- token extraction (pass-through auth) ----------------------------------
def test_extract_token_from_x_tapis_header():
    assert server.extract_tapis_token({"x-tapis-token": "abc123"}) == "abc123"


def test_missing_token_fails_cleanly():
    with pytest.raises(ToolError):
        server.extract_tapis_token({})


# --- inspect forwards the token verbatim -----------------------------------
@respx.mock
def test_inspect_forwards_token_and_body():
    # inspect always returns a LIST of per-file verdicts (a file -> a list of one).
    route = respx.post(f"{BASE}/files/inspect").mock(
        return_value=httpx.Response(
            200, json=[{"path": fx("rgbsmall.tif"), "is_geospatial": True, "kind": "raster"}]
        )
    )
    out = server.geoapi_inspect("tok-INSPECT", "designsafe.storage", fx("rgbsmall.tif"))

    assert isinstance(out, list) and len(out) == 1
    assert out[0]["is_geospatial"] is True and out[0]["kind"] == "raster"
    req = route.calls.last.request
    assert req.headers["X-Tapis-Token"] == "tok-INSPECT"
    assert json.loads(req.content) == {
        "system_id": "designsafe.storage",
        "path": fx("rgbsmall.tif"),
        "recursive": True,
    }


# --- list forwards the token, returns the entry list -----------------------
@respx.mock
def test_list_forwards_token_and_body():
    route = respx.post(f"{BASE}/files/list").mock(
        return_value=httpx.Response(
            200,
            json=[{"path": fx("rgbsmall.tif"), "extension": ".tif", "geospatial": "maybe"}],
        )
    )
    out = server.geoapi_list("tok-LIST", "designsafe.storage", "/some/dir")

    assert isinstance(out, list) and out[0]["geospatial"] == "maybe"
    req = route.calls.last.request
    assert req.headers["X-Tapis-Token"] == "tok-LIST"
    assert json.loads(req.content) == {
        "system_id": "designsafe.storage",
        "path": "/some/dir",
        "recursive": True,
    }


# --- import routes by kind, forwards the token -----------------------------
@respx.mock
def test_import_raster_routes_to_tile_servers():
    route = respx.post(f"{BASE}/projects/7/tile-servers/files/import/").mock(
        return_value=httpx.Response(201, json=[{"id": 1, "status": "QUEUED"}])
    )
    out = server.geoapi_import("tok-R", 7, "sys", fx("rgbsmall.tif"))

    assert out == [{"id": 1, "status": "QUEUED"}]
    req = route.calls.last.request
    assert req.headers["X-Tapis-Token"] == "tok-R"
    assert json.loads(req.content) == {"files": [{"system": "sys", "path": fx("rgbsmall.tif")}]}


@respx.mock
def test_import_vector_routes_to_features():
    route = respx.post(f"{BASE}/projects/7/features/files/import/").mock(
        return_value=httpx.Response(200, json={"message": "Task created for file import"})
    )
    out = server.geoapi_import("tok-V", 7, "sys", fx("geojson.json"))

    assert out["message"] == "Task created for file import"
    assert route.calls.last.request.headers["X-Tapis-Token"] == "tok-V"


@respx.mock
def test_import_image_routes_to_features():
    route = respx.post(f"{BASE}/projects/3/features/files/import/").mock(
        return_value=httpx.Response(200, json={"message": "ok"})
    )
    server.geoapi_import("tok-I", 3, "sys", "/some/photo.jpg")
    assert route.called


@respx.mock
def test_import_pointcloud_rejected_without_calling_geoapi():
    route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200))
    with pytest.raises(ToolError):
        server.geoapi_import("tok-P", 7, "sys", fx("lidar_subset_las1pt2.las"))
    assert not route.called  # never hit GeoAPI


# --- GeoAPI errors surface cleanly (token never leaked in message) ---------
@respx.mock
def test_geoapi_error_surfaces_as_toolerror():
    respx.post(f"{BASE}/files/inspect").mock(
        return_value=httpx.Response(401, text="Invalid token")
    )
    with pytest.raises(ToolError) as exc:
        server.geoapi_inspect("tok-SECRET", "sys", fx("not_geospatial.txt"))
    assert "401" in str(exc.value)
    assert "tok-SECRET" not in str(exc.value)


# --- maps: list + create forward the token --------------------------------
@respx.mock
def test_list_maps_forwards_token():
    route = respx.get(f"{BASE}/projects/").mock(
        return_value=httpx.Response(200, json=[{"id": 7, "name": "My Map"}])
    )
    out = server.geoapi_list_maps("tok-MAPS")

    assert out == [{"id": 7, "name": "My Map"}]
    assert route.calls.last.request.headers["X-Tapis-Token"] == "tok-MAPS"


def _jwt(username: str) -> str:
    """A fake unsigned JWT carrying just the tapis/username claim (for tapis_username)."""
    import base64

    payload = (
        base64.urlsafe_b64encode(json.dumps({"tapis/username": username}).encode())
        .rstrip(b"=")
        .decode()
    )
    return f"header.{payload}.sig"


def test_resolve_my_data_alias():
    jwt = _jwt("nathanf")
    # "DESIGN_SAFE_MY_DATA" -> designsafe.storage.default rooted at /<username>, path is home-relative
    assert server.resolve_location(jwt, "DESIGN_SAFE_MY_DATA", "/img1.jpg") == (
        "designsafe.storage.default",
        "/nathanf/img1.jpg",
    )
    assert server.resolve_location(jwt, "DESIGN_SAFE_MY_DATA", "") == (
        "designsafe.storage.default",
        "/nathanf",
    )
    assert server.resolve_location(jwt, "DESIGN_SAFE_MY_DATA", "/") == (
        "designsafe.storage.default",
        "/nathanf",
    )
    # any real system passes through unchanged
    assert server.resolve_location(jwt, "designsafe.storage.published", "/PRJ-1") == (
        "designsafe.storage.published",
        "/PRJ-1",
    )


@respx.mock
def test_create_map_my_data_builds_payload():
    route = respx.post(f"{BASE}/projects/").mock(
        return_value=httpx.Response(200, json={"id": 9})
    )
    out = server.geoapi_create_map(_jwt("nathanf"), "New Map", "desc", "DESIGN_SAFE_MY_DATA")

    assert out["id"] == 9
    body = json.loads(route.calls.last.request.content)
    assert body["system_id"] == "designsafe.storage.default"
    assert body["system_path"] == "/nathanf"  # derived from the JWT username
    assert body["system_file"] == "New_Map"  # spaces -> underscores
    assert body["watch_users"] is False
    assert body["watch_content"] is False  # never scrape the directory
    assert body["public"] is False  # never public via the MCP


@respx.mock
def test_create_map_project_uses_given_system():
    route = respx.post(f"{BASE}/projects/").mock(
        return_value=httpx.Response(200, json={"id": 5})
    )
    server.geoapi_create_map(_jwt("nathanf"), "Proj Map", "", "project-1234")

    body = json.loads(route.calls.last.request.content)
    assert body["system_id"] == "project-1234"
    assert body["watch_users"] is True  # DesignSafe project -> watch users


@respx.mock
def test_create_map_blank_location_is_rejected():
    # A blank location has no system -> refuse before POSTing (GeoAPI only logs).
    route = respx.post(f"{BASE}/projects/").mock(return_value=httpx.Response(200))
    for bad in ("", "   "):
        with pytest.raises(ToolError):
            server.geoapi_create_map(_jwt("nathanf"), "Map", "", bad)
    assert not route.called


def test_tools_are_registered():
    import asyncio

    async def _names():
        return [
            (await server.mcp.get_tool(n)).name
            for n in ("list_files", "inspect_file", "import_file", "list_maps", "create_map")
        ]

    assert asyncio.run(_names()) == [
        "list_files",
        "inspect_file",
        "import_file",
        "list_maps",
        "create_map",
    ]


def test_read_only_annotations():
    # Reads are marked read-only so clients can skip the approval prompt; writes are not.
    import asyncio

    async def _ro(name):
        return (await server.mcp.get_tool(name)).annotations.readOnlyHint

    assert asyncio.run(_ro("list_files")) is True
    assert asyncio.run(_ro("inspect_file")) is True
    assert asyncio.run(_ro("list_maps")) is True
    assert asyncio.run(_ro("import_file")) is False
    assert asyncio.run(_ro("create_map")) is False
