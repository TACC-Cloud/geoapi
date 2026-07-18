import base64
import json
import os
import re
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers

GEOAPI_BASE_URL = os.environ.get("GEOAPI_BASE_URL", "http://geoapi:8000").rstrip("/")
HTTP_TIMEOUT_SECONDS = float(os.environ.get("GEOAPI_HTTP_TIMEOUT", "60"))

# TODO Remove later
# Kind routing for import_file. Anything not raster/pointcloud goes to the general
# feature import (GeoJSON, shapefile, GPX, georeferenced images).
RASTER_EXTS = (".tif", ".tiff", ".geotiff")
POINTCLOUD_EXTS = (".las", ".laz", ".copc")

mcp = FastMCP("geoapi-mcp")


def extract_tapis_token(headers: dict[str, str]) -> str:
    """Pull the caller's Tapis JWT from the ``X-Tapis-Token`` request header
    (keys are lower-cased). Raises a clean ToolError if it's missing. Never logs it.
    """
    token = headers.get("x-tapis-token")
    if not token:
        raise ToolError("Missing Tapis token: send X-Tapis-Token.")
    return token


def tapis_username(token: str) -> str:
    """Read the ``tapis/username`` claim from the JWT payload. No signature check --
    GeoAPI validates the token; we only need the name (e.g. to build the My Data path)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # pad to a multiple of 4
        return json.loads(base64.urlsafe_b64decode(payload))["tapis/username"]
    except Exception:
        raise ToolError("Could not read the username from the Tapis token.")


# A distinctive alias (not a plausible real Tapis system id, so it can't be shadowed by
# a user's actual system) that the file tools + create_map resolve to My Data.
MY_DATA_ALIAS = "DESIGN_SAFE_MY_DATA"
DESIGNSAFE_MYDATA_SYSTEM = "designsafe.storage.default"


def resolve_location(token: str, system_id: str, path: str) -> tuple[str, str]:
    """Resolve the ``"DESIGN_SAFE_MY_DATA"`` alias to the user's DesignSafe My Data -- system
    ``designsafe.storage.default`` rooted at ``/<username>`` (decoded from the token).
    ``path`` is treated as relative to that home ("" -> the home root). Any other
    ``system_id`` (a real Tapis system) is returned unchanged with an absolute path.
    """
    if system_id == MY_DATA_ALIAS:
        sub = path.strip().strip("/")
        home = f"/{tapis_username(token)}"
        return DESIGNSAFE_MYDATA_SYSTEM, (f"{home}/{sub}" if sub else home)
    return system_id, path


def _post_geoapi(token: str, endpoint: str, json_body: dict) -> Any:
    """POST to GeoAPI."""
    resp = httpx.post(
        f"{GEOAPI_BASE_URL}{endpoint}",
        json=json_body,
        headers={"X-Tapis-Token": token},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    if resp.status_code >= 400:
        raise ToolError(f"GeoAPI returned {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def _get_geoapi(token: str, endpoint: str) -> Any:
    """GET from GeoAPI."""
    resp = httpx.get(
        f"{GEOAPI_BASE_URL}{endpoint}",
        headers={"X-Tapis-Token": token},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    if resp.status_code >= 400:
        raise ToolError(f"GeoAPI returned {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def geoapi_list(
    token: str, system_id: str, path: str, recursive: bool = True
) -> list[dict[str, Any]]:
    return _post_geoapi(
        token,
        "/files/list",
        {"system_id": system_id, "path": path, "recursive": recursive},
    )


def geoapi_inspect(
    token: str, system_id: str, path: str, recursive: bool = True
) -> list[dict[str, Any]]:
    return _post_geoapi(
        token,
        "/files/inspect",
        {"system_id": system_id, "path": path, "recursive": recursive},
    )


def geoapi_import(
    token: str, project_id: int, system_id: str, path: str
) -> dict[str, Any]:
    """Route to the correct existing GeoAPI import endpoint by file kind."""
    ext = os.path.splitext(path)[1].lower()
    if ext in POINTCLOUD_EXTS:
        # TODO(WG-675): point-cloud import is a two-step flow -- create a PointCloud
        # record, then POST /projects/{id}/point-cloud/{point_cloud_id}/import/.
        # Deferred for now; wire it up when point-cloud support is needed. Probably
        # best to have a one-step flow in geoapi
        raise ToolError(
            "Point-cloud import is not supported yet (needs the two-step "
            "point-cloud create-then-import flow)."
        )
    if ext in RASTER_EXTS:
        endpoint = f"/projects/{project_id}/tile-servers/files/import/"
    else:
        endpoint = f"/projects/{project_id}/features/files/import/"
    # Existing import endpoints take a batch {files:[...]}; we send the single file.
    return _post_geoapi(token, endpoint, {"files": [{"system": system_id, "path": path}]})


def geoapi_list_maps(token: str) -> list[dict[str, Any]]:
    return _get_geoapi(token, "/projects/")


def geoapi_create_map(
    token: str, name: str, description: str, location: str
) -> dict[str, Any]:
    """Build the create-project payload for the chosen location and POST it.

    ``location`` is either the My Data alias (-> designsafe.storage.default at
    /<username>) or a Tapis project system id like "project-XXXX". Always PRIVATE (public
    is set False -- publishing goes through the Hazmapper web app). The map needs a Tapis
    system+path so GeoAPI can write its .hazmapper marker file there.
    """
    system_file = re.sub(r"\s+", "_", name.strip()) or "map"
    if location == MY_DATA_ALIAS:
        system_id = "designsafe.storage.default"
        system_path = f"/{tapis_username(token)}"
        watch_users = False
    else:
        system_id = location  # a Tapis project system id, e.g. "project-1234"
        system_path = "/"
        watch_users = location.startswith("project-")
    body = {
        "name": name,
        "description": description,
        "system_id": system_id,
        "system_path": system_path,
        "system_file": system_file,
        "watch_users": watch_users,
        # Never sync/scrape the directory's contents into the map (see create_map docs).
        "watch_content": False,
        "public": False,
    }
    return _post_geoapi(token, "/projects/", body)


@mcp.tool(annotations={"readOnlyHint": True})
def list_files(
    system_id: str, path: str, recursive: bool = True
) -> list[dict[str, Any]]:
    """List a Tapis path and return a CHEAP, extension-only geospatial guess per file.

    ``path`` may be a single file OR a directory. Returns a LIST of entries, each with
    ``type`` (``"file"`` | ``"dir"``), ``path``, ``size``, ``extension``, and
    ``geospatial`` (``"yes"`` | ``"no"`` | ``"maybe"``, null for dirs) -- a guess from
    the extension alone, NOT a verdict.

    ``recursive`` (default true) walks the whole tree and returns every file. Pass
    ``recursive=false`` for a quick, shallow ``ls`` of just the immediate children (files
    and folders) -- prefer this to peek at a large directory, then drill into a ``dir``
    entry. Then call ``inspect_file`` on the promising files (``"yes"``/``"maybe"``).

    For the user's **My Data** (their DesignSafe Data Depot storage), pass
    ``system_id="DESIGN_SAFE_MY_DATA"`` and a path relative to their home (``""`` = home root, or e.g.
    ``"/photos"`` / ``"/img1.jpg"``). This MCP resolves it to
    ``designsafe.storage.default`` at ``/<username>`` for you -- you do NOT need to know
    or ask for the username. For any other Tapis system, pass its real system id and an
    absolute path.
    """
    token = extract_tapis_token(get_http_headers(include_all=True))
    system_id, path = resolve_location(token, system_id, path)
    return geoapi_list(token, system_id, path, recursive)


@mcp.tool(annotations={"readOnlyHint": True})
def inspect_file(
    system_id: str, path: str, recursive: bool = True
) -> list[dict[str, Any]]:
    """Inspect a Tapis path and return DETERMINISTIC geospatial verdicts.

    ``path`` may be a single file OR a directory. Returns a LIST of verdicts, one per
    file (a file yields a list of one); each item names its ``path``. The verdict
    (``is_geospatial``, ``kind``, ``crs``, ``bounds``, ...) is decided deterministically
    by GDAL/OGR/PDAL (and EXIF for photos), never by you. ``kind`` is one of ``raster``,
    ``vector``, ``pointcloud``, or ``image`` -- an ``image`` is a geotagged photo
    (``is_geospatial: true`` via its EXIF location). Relay each ``detail`` to the user.

    ``recursive`` (default true) inspects every file under a directory -- this fetches
    and runs GDAL on EACH file, so it is expensive for a big tree. Pass
    ``recursive=false`` to inspect only the immediate files, or (cheaper still) survey
    with ``list_files`` first and inspect just the promising ones.

    For the user's **My Data**, pass ``system_id="DESIGN_SAFE_MY_DATA"`` and a path relative to their
    home (``""`` = home root); this MCP fills in ``designsafe.storage.default`` at
    ``/<username>`` -- no need to know or ask for the username. Other systems: real system
    id + absolute path.

    Use this to triage files BEFORE any import. For a file whose ``is_geospatial`` is
    true, ASK THE USER to confirm before calling ``import_file``. Never import a file
    whose verdict is false -- it is not geospatial.
    """
    token = extract_tapis_token(get_http_headers(include_all=True))
    system_id, path = resolve_location(token, system_id, path)
    return geoapi_inspect(token, system_id, path, recursive)


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False})
def import_file(
    system_id: str, path: str, project_id: int, label: str | None = None
) -> dict[str, Any]:
    """Import a geospatial Tapis file into a map/project (asynchronous, WRITE).

    ONLY call this after ``inspect_file`` reported ``is_geospatial: true`` AND the user
    explicitly confirmed the import. NEVER import a non-geospatial file.

    WARNING -- this mutates a shared map. Do NOT add files unless the user is certain
    they should. Pre-flight: call ``list_maps`` and find the target ``project_id``.
      * If it is NOT in the list, do NOT import -- the user has no access (GeoAPI 403s).
      * If it IS listed but its ``creator``/``admin`` are both false, the user is a
        collaborator, NOT the owner -- warn them clearly and get explicit confirmation
        before adding files to someone else's map.
    Always confirm the exact ``project_id`` with the user first; when unsure, ask rather
    than import.

    Supports rasters (routed to the tile-server import) and vectors/georeferenced
    images (routed to the feature import). Point clouds are not supported yet.

    ``label`` is accepted for a human-friendly name but is not currently consumed by
    the underlying import endpoints. For a file in the user's **My Data**, pass
    ``system_id="DESIGN_SAFE_MY_DATA"`` and a home-relative path (this MCP resolves the username).
    """
    token = extract_tapis_token(get_http_headers(include_all=True))
    system_id, path = resolve_location(token, system_id, path)
    return geoapi_import(token, project_id, system_id, path)


@mcp.tool(annotations={"readOnlyHint": True})
def list_maps() -> list[dict[str, Any]]:
    """List the maps (projects) the current user can access.

    Returns the user's OWN maps only (scoped to their token). Each has ``id``, ``name``,
    ``uuid``, ``description``, ``public``, and the caller's role on that map: ``creator``
    and ``admin`` (booleans). Use a map's ``id`` as the ``project_id`` for ``import_file``.
    "The target map is in this list" means the user may add files to it; ``creator``/
    ``admin`` tell you whether they own it or are just a member.
    """
    token = extract_tapis_token(get_http_headers(include_all=True))
    return geoapi_list_maps(token)


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False})
def create_map(
    name: str, description: str = "", location: str = MY_DATA_ALIAS
) -> dict[str, Any]:
    """Create a new **private** map (project) owned by the current user.

    A map has to live somewhere in DesignSafe storage. ASK THE USER where before calling:
      * ``location="DESIGN_SAFE_MY_DATA"`` (default): the user's personal storage in the DesignSafe
        Data Depot -- the area called "My Data" (system ``designsafe.storage.default`` at
        ``/<their-username>``).
      * a DesignSafe **project**: pass the project's Tapis system id as ``location``
        (it looks like ``project-XXXXXXXX``). We can't list the user's projects yet, so
        if they want a project, ask them for the exact Tapis system id.

    Creating a map inside a DesignSafe **project** is the typical workflow: the user builds
    the map on their project data, then later (in DesignSafe / the Hazmapper web app)
    publishes the project and makes the map public. So a project is usually the right
    location when the user is working with project data.

    This is a WRITE -- confirm the name AND location with the user first. Returns the new
    map incl. its ``id`` (use as ``project_id`` for ``import_file``).

    This tool never enables folder syncing. WARN the user: if syncing were on, GeoAPI
    would scrape and import EVERY file under the map's directory (for My Data that is the
    user's whole home) -- so it is deliberately left off here.

    Maps are always created PRIVATE, by design -- do NOT try to make one public here.
    Publishing is a deliberate step in the Hazmapper web app, which walks the user through
    checking the map's data is published first. Have them publish there, later.
    """
    token = extract_tapis_token(get_http_headers(include_all=True))
    return geoapi_create_map(token, name, description, location)


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=os.environ.get("MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_PORT", "8001")),
    )
