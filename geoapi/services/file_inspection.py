"""File inspection ALL inspection runs on celery task.

TODO: the synchronous wait is a stopgap. It will be refactored to a async. So only now
reasonable ot use with small input (few files or small file.

TODO: multi-file vector formats (shapefile .shp + .shx/.dbf/.prj) are not handled
yet (fetching a lone .shp is not enough for OGR. The sidecars must be fetched alongside.
"""

import json
import os
import re
import subprocess

from geoapi.exceptions import ApiException
from geoapi.log import logger
from geoapi.models import User
from geoapi.schema.files import FileInspectResponse, FileListEntry
from geoapi.utils.external_apis import TapisUtils

POINTCLOUD_EXTS = (".las", ".laz", ".copc")
VECTOR_EXTS = (".geojson", ".json", ".shp", ".gpkg", ".gpx", ".kml", ".kmz", ".fgb")
IMAGE_EXTS = (".jpg", ".jpeg")

DESIGNSAFE_MYDATA_SYSTEM = "designsafe.storage.default"


def validate_listing_path(system_id: str, path: str) -> None:
    """Reject a root path on My Data """
    if system_id == DESIGNSAFE_MYDATA_SYSTEM and path.strip() in ("", "/"):
        raise ApiException(
            f"Refusing to list the root of '{DESIGNSAFE_MYDATA_SYSTEM}' -- that is the "
            "shared storage root (every user's home). Target a specific user directory "
            "instead, e.g. /<username> or /<username>/some/folder."
        )

# Cheap extension-only geospatial guess for /files/list (NOT a verdict -- /files/inspect
# is the real thing). "yes" = formats that are geospatial by definition; "maybe" = could
# go either way (a .tif may be a plain image, a .json may not be GeoJSON, an image may be
# geotagged); everything else "no".
_EXT_GEOSPATIAL_YES = {
    ".shp", ".gpkg", ".geojson", ".gpx", ".kml", ".kmz", ".fgb",
    ".las", ".laz", ".copc",
}
_EXT_GEOSPATIAL_MAYBE = {".tif", ".tiff", ".json", ".jpg", ".jpeg", ".png"}

# Partial read: for COG and header-first formats the metadata lives at the front of the
# file, so fetching just this many bytes is enough. If the partial parse fails (e.g. a
# non-COG TIFF whose IFD lives elsewhere) we fall back to a full fetch.
PARTIAL_READ_BYTES = 512 * 1024  # 512 KB

SUBPROCESS_TIMEOUT_SECONDS = 60


def list_tapis_entries(
    client,
    system_id: str,
    path: str,
    recursive: bool = True,
    _seen: set[str] | None = None,
):
    """List entries (``TapisFileListing``) under a Tapis path.

    ``client`` is a ``geoapi.utils.external_apis.TapisUtils``. A file path lists to itself.
    For a directory: if ``recursive`` we descend and return every FILE under the tree
    (dirs are walked, not returned, like ``find -type f``); if not, we return the
    immediate children -- files AND dirs (like ``ls``). ``_seen`` guards cycles. Entries
    carry ``.type``, ``.path``, ``.size``.
    """
    if _seen is None:
        _seen = set()
    if path in _seen:
        return []
    _seen.add(path)

    entries = []
    for item in client.listing(system_id, path):
        item_path = str(item.path)
        if item.type == "dir" and not item_path.endswith(".Trash"):
            if recursive:
                entries.extend(
                    list_tapis_entries(client, system_id, item_path, recursive, _seen)
                )
            else:
                entries.append(item)
        elif item.type == "file":
            entries.append(item)
    return entries


def list_tapis_files(
    client, system_id: str, path: str, recursive: bool = True
) -> list[str]:
    return [
        str(e.path)
        for e in list_tapis_entries(client, system_id, path, recursive)
        if e.type == "file"
    ]


def _extension_geospatial_guess(ext: str) -> str:
    if ext in _EXT_GEOSPATIAL_YES:
        return "yes"
    if ext in _EXT_GEOSPATIAL_MAYBE:
        return "maybe"
    return "no"


def _run_tool(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a blocking geospatial CLI tool. Never raises on non-zero exit; the caller
    inspects returncode/stdout. Never logs file contents or tokens."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


def _extract_epsg(text) -> str | None:
    """Best-effort 'EPSG:1234' from a WKT/PROJJSON blob (str or already-parsed dict).
    Returns None if not found."""
    if not text:
        return None
    if not isinstance(text, str):
        text = json.dumps(text)
    # PROJJSON: {"id": {"authority": "EPSG", "code": 4326}} -- take the LAST match,
    # which is the outermost (compound/geographic) CRS id.
    matches = re.findall(r'"authority"\s*:\s*"EPSG"\s*,\s*"code"\s*:\s*(\d+)', text)
    if matches:
        return f"EPSG:{matches[-1]}"
    # WKT: ... ID["EPSG",4326]] or AUTHORITY["EPSG","4326"]
    m = re.findall(r'(?:ID|AUTHORITY)\[\s*"EPSG"\s*,\s*"?(\d+)"?\s*\]', text)
    if m:
        return f"EPSG:{m[-1]}"
    return None


def _bounds_from_corners(corners: dict) -> list[float] | None:
    """Compute [minx, miny, maxx, maxy] from gdalinfo cornerCoordinates."""
    pts = [
        corners.get(k)
        for k in ("upperLeft", "lowerLeft", "upperRight", "lowerRight")
        if corners.get(k)
    ]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def _inspect_pointcloud(local_path: str) -> FileInspectResponse | None:
    proc = _run_tool(["pdal", "info", "--summary", local_path])
    if proc.returncode != 0:
        return None
    try:
        summary = json.loads(proc.stdout).get("summary", {})
    except json.JSONDecodeError:
        return None
    if not summary:
        return None

    b = summary.get("bounds", {})
    bounds = None
    if all(k in b for k in ("minx", "miny", "maxx", "maxy")):
        bounds = [b["minx"], b["miny"], b["maxx"], b["maxy"]]
    srs = summary.get("srs", {})
    crs = _extract_epsg(srs.get("json", "")) or _extract_epsg(srs.get("wkt", ""))
    if not crs and srs.get("proj4"):
        crs = srs["proj4"]
    n_points = summary.get("num_points")

    driver = "LAZ" if local_path.lower().endswith(".laz") else "LAS"
    crs_note = f"CRS {crs}" if crs else "no CRS (not georeferenced)"
    detail = f"{driver} point cloud, {n_points} points, {crs_note}."
    return FileInspectResponse(
        is_geospatial=True,
        kind="pointcloud",
        driver=driver,
        crs=crs,
        bounds=bounds,
        size=None,
        bands=None,
        detail=detail,
    )


def _inspect_raster(local_path: str) -> FileInspectResponse | None:
    info = _gdalinfo_json(local_path)
    if info is None:
        return None

    driver = info.get("driverShortName")
    size = info.get("size")
    bands = len(info.get("bands", [])) or None
    wkt = info.get("coordinateSystem", {}).get("wkt", "")
    has_gcps = bool(info.get("gcps"))
    georeferenced = bool(wkt) or has_gcps
    crs = _extract_epsg(wkt)
    bounds = _bounds_from_corners(info.get("cornerCoordinates", {}))
    dims = f"{size[0]}x{size[1]}" if size else "?"

    if georeferenced:
        detail = (
            f"Georeferenced {driver} raster, {dims}, "
            f"{bands or 0} band(s), CRS {crs or 'present'}."
        )
        return FileInspectResponse(
            is_geospatial=True,
            kind="raster",
            driver=driver,
            crs=crs,
            bounds=bounds if wkt else None,
            size=size,
            bands=bands,
            detail=detail,
        )
    # Parses as a raster but has no CRS -> a plain image, not geospatial.
    detail = (
        f"{driver} image, {dims}, with no CRS -- looks like a plain "
        "(non-georeferenced) image, not geospatial."
    )
    return FileInspectResponse(
        is_geospatial=False,
        kind=None,
        driver=driver,
        crs=None,
        bounds=None,
        size=size,
        bands=bands,
        detail=detail,
    )


def _inspect_vector(local_path: str) -> FileInspectResponse | None:
    proc = _run_tool(["ogrinfo", "-json", "-al", "-so", local_path])
    if proc.returncode != 0:
        return None
    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None

    layers = info.get("layers", [])
    geom_field = None
    for layer in layers:
        gfs = layer.get("geometryFields", [])
        if gfs and gfs[0].get("type"):
            geom_field = gfs[0]
            break
    # No geometry column -> not a spatial vector (e.g. a plain JSON/CSV).
    if geom_field is None:
        return None

    driver = info.get("driverShortName")
    geom_type = geom_field.get("type")
    extent = geom_field.get("extent")  # [minx, miny, maxx, maxy]
    crs = _extract_epsg(
        json.dumps(geom_field.get("coordinateSystem", {}).get("projjson", {}))
    ) or _extract_epsg(geom_field.get("coordinateSystem", {}).get("wkt", ""))
    detail = f"{driver} vector with {geom_type} geometry, CRS {crs or 'unspecified'}."
    return FileInspectResponse(
        is_geospatial=True,
        kind="vector",
        driver=driver,
        crs=crs,
        bounds=extent if extent and len(extent) == 4 else None,
        size=None,
        bands=None,
        detail=detail,
    )


def _gdalinfo_json(path: str) -> dict | None:
    proc = _run_tool(["gdalinfo", "-json", path])
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def _inspect_image(local_path: str) -> FileInspectResponse | None:
    """A photo is 'geospatial' if it carries an EXIF GPS location.
    """
    from geoapi.exceptions import InvalidEXIFData
    from geoapi.services.images import get_exif_location

    try:
        with open(local_path, "rb") as f:
            loc = get_exif_location(f)
    except InvalidEXIFData:
        return None
    except Exception:
        # Unreadable/corrupt EXIF -> treat as no geolocation (fall back to plain image).
        return None

    detail = (
        f"Geotagged image at lat {loc.latitude:.5f}, lon {loc.longitude:.5f} -- "
        "importable to Hazmapper as a point feature."
    )
    return FileInspectResponse(
        is_geospatial=True,
        kind="image",
        driver="JPEG",
        crs="EPSG:4326",  # EXIF GPS is WGS84
        bounds=[loc.longitude, loc.latitude, loc.longitude, loc.latitude],
        size=None,
        bands=None,
        detail=detail,
    )


def _probe_local(local_path: str, ext: str) -> FileInspectResponse | None:
    """Route a fetched local file to the right tool by extension hint (tool-decided)."""
    if ext in POINTCLOUD_EXTS:
        return _inspect_pointcloud(local_path)
    if ext in VECTOR_EXTS:
        return _inspect_vector(local_path) or _inspect_raster(local_path)
    if ext in IMAGE_EXTS:
        # Geotagged -> geospatial image; otherwise a plain (non-geospatial) image.
        return _inspect_image(local_path) or _inspect_raster(local_path)
    return _inspect_raster(local_path) or _inspect_vector(local_path)


def probe(client: TapisUtils, system_id: str, path: str) -> FileInspectResponse:
    """Fetch a single file from Tapis and probe it for a deterministic geospatial verdict
    via GDAL/OGR/PDAL (and EXIF for photos).

    ``client`` is a ``geoapi.utils.external_apis.TapisUtils``. This is the WORKER-side
    logic: it needs the geo CLIs and can be slow, so it runs inside the Celery task, not
    in the API. Routing is extension-hinted but tool-decided; anything none of the tools
    recognize as spatial is reported ``is_geospatial=False``.
    """
    ext = os.path.splitext(path)[1].lower()

    # Partial fetch first: enough for header-first formats (COG raster, LAS/LAZ point
    # clouds, JPEG EXIF) and avoids pulling huge files. Small files come back whole.
    prefix = client.getFilePartial(system_id, path, PARTIAL_READ_BYTES)
    try:
        result = _probe_local(prefix.name, ext)
    finally:
        prefix.close()

    # Full-file fallback: a non-COG raster can keep its IFD at the END, so the prefix
    # parse fails. Re-fetch the whole file once and retry.
    # TODO and fetch shapefile sidecars alongside.
    if result is None:
        full = client.getFile(system_id, path)
        try:
            result = _probe_local(full.name, ext)
        finally:
            full.close()

    if result is None:
        logger.info(f"inspect: '{path}' on '{system_id}' is not geospatial")
        result = FileInspectResponse(
            is_geospatial=False,
            kind=None,
            driver=None,
            crs=None,
            bounds=None,
            size=None,
            bands=None,
            detail=(
                "Not recognized as geospatial by GDAL/OGR/PDAL -- likely a "
                "non-spatial file."
            ),
        )
    result.system = system_id
    result.path = path
    return result


class FileInspectionService:
    @staticmethod
    def inspect(
        user_id: int, system_id: str, path: str, recursive: bool = True
    ) -> list[FileInspectResponse]:
        """Dispatch inspection to the worker and *currently* blocks on the result.

        TODO: this synchronous wait is a stopgap --> it keeps the endpoint
        returning verdicts inline while we only test on small inputs. Still to finalize:
        a bounded/configurable wait timeout  and the move to a truly
        async submit
        """
        validate_listing_path(system_id, path)  # fail fast, before dispatching
        from geoapi.tasks.file_inspection import inspect_files

        async_result = inspect_files.apply_async(
            args=[user_id, system_id, path, recursive], queue="default"
        )
        data = async_result.get(timeout=SUBPROCESS_TIMEOUT_SECONDS)
        return [FileInspectResponse(**item) for item in data]

    @staticmethod
    def list_files(
        session, user_id: int, system_id: str, path: str, recursive: bool = True
    ) -> list[FileListEntry]:
        """synchronous listing with an extension-only geospatial guess per file.

        Unlike inspect() this needs no geo CLIs and fetches nothing, so it runs in the
        API rather than on the worker. ``recursive`` (default true) descends into
        sub-directories; if false, returns the immediate children (files and folders).

        TODO: for a huge directory this recursive Tapis listing can still be slow -- the
        same async refactor noted on inspect() applies.
        """
        validate_listing_path(system_id, path)
        user = session.get(User, user_id)
        client = TapisUtils(session, user)
        results: list[FileListEntry] = []
        for item in list_tapis_entries(client, system_id, path, recursive):
            item_path = str(item.path)
            if item.type == "dir":
                results.append(
                    FileListEntry(system=system_id, path=item_path, type="dir")
                )
                continue
            ext = os.path.splitext(item_path)[1].lower()
            results.append(
                FileListEntry(
                    system=system_id,
                    path=item_path,
                    type="file",
                    size=item.size,
                    extension=ext,
                    geospatial=_extension_geospatial_guess(ext),
                )
            )
        return results
