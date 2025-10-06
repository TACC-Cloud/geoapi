import os
import json
import subprocess
import math
from pathlib import Path
from uuid import uuid4

from geoapi.utils.assets import (
    make_project_asset_dir,
    delete_assets,
)

from geoapi.celery_app import app
from geoapi.db import create_task_session
from geoapi.log import logger
from geoapi.models import Task, TaskStatus, TileServer, User
from geoapi.utils.external_apis import TapisUtils, TapisFileGetError
from geoapi.tasks.utils import send_progress_update
from geoapi.schema.tapis import TapisFilePath


ASSETS_DIR = Path(os.getenv("ASSETS_BASE_DIR", "/assets")).resolve()


def _validate_raster_name(name: str) -> None:
    ok = (".tif", ".tiff", ".geotiff")
    if not name.lower().endswith(ok):
        raise ValueError(
            f"Unsupported raster extension for '{name}'. Expected one of {ok}"
        )


def gdal_cogify(src: Path, dst: Path) -> None:
    """Convert to COG"""
    # When creating cog, we convert to Web Mercator and use GoogleMapsCompatible
    cmd = [
        "gdalwarp",
        "-of",
        "COG",
        "-t_srs",
        "EPSG:3857",  #  Web Mercator
        "-co",
        "COMPRESS=DEFLATE",
        "-co",
        "TILING_SCHEME=GoogleMapsCompatible",
        str(src),
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def get_cog_metadata(path: Path) -> dict:
    """
    Extract useful metadata from a COG for tileOptions.

    IMPORTANT: This function assumes the COG is in Web Mercator (EPSG:3857) projection.
    The zoom level calculations are based on Web Mercator's resolution at the equator
    and will be incorrect for other projections.

    Raises:
        ValueError: If the COG is not in EPSG:3857 (Web Mercator) projection
    """
    result = subprocess.run(
        ["gdalinfo", "-json", str(path)], capture_output=True, text=True, check=True
    )
    info = json.loads(result.stdout)

    # Verify the COG is in Web Mercator
    srs = info.get("coordinateSystem", {}).get("wkt", "")
    if "3857" not in srs and "Pseudo-Mercator" not in srs:
        raise ValueError(
            f"COG must be in EPSG:3857 (Web Mercator) for accurate zoom calculation. "
            f"Found: {srs[:100]}..."
        )

    # Get bounds
    polygon = info.get("wgs84Extent", {}).get("coordinates", [[]])[0]
    lngs = [coord[0] for coord in polygon]
    lats = [coord[1] for coord in polygon]
    bounds = [[min(lats), min(lngs)], [max(lats), max(lngs)]]

    # Get base pixel size and image dimensions
    pixel_size = abs(info["geoTransform"][1])  # In meters (Web Mercator)
    base_width = info["size"][0]
    base_height = info["size"][1]

    # Calculate base zoom level
    # Use ceil() to round up. For example, if pixel size is 0.075m and log2 gives 20.99,
    # the data is closer to zoom 21 resolution than zoom 20, so round up to 21
    # Formula: zoom level where 1 pixel = pixel_size meters (at equator in Web Mercator)
    base_zoom = math.ceil(math.log2(156543.03 / pixel_size))

    logger.info(f"=== COG Analysis: {path.name} ===")
    logger.info(f"Base image size: {base_width}x{base_height}")
    logger.info(f"Base pixel size: {pixel_size:.6f} meters")
    logger.info(f"Calculated base zoom: {base_zoom}")

    max_zoom = min(max(base_zoom, 0), 24)
    logger.info(f"maxZoom: {max_zoom}")

    return {
        "minZoom": 0,
        "maxZoom": max_zoom,
        "maxNativeZoom": max_zoom,
        "bounds": bounds,
    }


@app.task(queue="heavy")
def import_tile_servers_from_tapis(
    user_id: int,
    tapis_file: dict,
    project_id: int,
    task_id: int,
) -> None:
    """
    Download raster from Tapis (system/path), store under:
        /assets/{projectId}/{uuid}/data.cog.tif
    If already a COG -> store as-is
    If not a COG -> convert to COG
    Then register a TileServer pointing to TiTiler.
    """

    tapis_file = TapisFilePath.model_validate(tapis_file)
    tmp_file = None
    with create_task_session() as session:
        try:
            user = session.get(User, user_id)
            client = TapisUtils(session, user)

            def _update_task_and_progress(
                status: TaskStatus = TaskStatus.RUNNING, latest_message: str = ""
            ) -> None:
                t = session.get(Task, task_id)
                t.status = status.value
                # t.latest_message = latest_message #  TODO
                session.add(t)
                session.commit()

                send_progress_update(
                    user, t.process_id, status.value.lower(), latest_message
                )

            try:
                _validate_raster_name(tapis_file.path)
            except ValueError as e:
                _update_task_and_progress(
                    status=TaskStatus.FAILED,
                    latest_message=f"Invalid file type: {str(e)}",
                )
                raise

            _update_task_and_progress(latest_message="Starting import")

            _validate_raster_name(tapis_file.path)

            _update_task_and_progress(latest_message=f"Fetching {tapis_file.path}")

            try:
                tmp_file = client.getFile(
                    tapis_file.system, tapis_file.path
                )  # temp file
            except TapisFileGetError:
                logger.exception(
                    f"Tapis getFile failed for {tapis_file} when "
                    f"creating tile server for user:{user.username}, project:{project_id})"
                )
                _update_task_and_progress(
                    status=TaskStatus.FAILED,
                    latest_message=f"Failed to get {tapis_file.path}",
                )
                raise RuntimeError(f"Failed to download {tapis_file.path}")

            cog_uuid = uuid4()
            cog_path = Path(make_project_asset_dir(project_id)) / f"{cog_uuid}.cog.tif"

            src_path = Path(tmp_file.name)

            _update_task_and_progress(latest_message="Processing file")
            gdal_cogify(src_path, cog_path)

            tile_options = get_cog_metadata(cog_path)

            # Create TileServer pointing to TiTiler
            ts = TileServer(
                project_id=project_id,
                name=tapis_file.path,
                type="xyz",
                kind="cog",
                internal=True,
                url=str(cog_path),  # e.g. /assets/{project_id}/{uuid}.cog.tif",
                attribution="",
                tileOptions=tile_options,
                uiOptions={
                    "zIndex": 0,  # frontend will readjust as needed
                    "opacity": 1,
                    "isActive": True,
                    "showInput": False,
                    "showDescription": False,
                },
            )
            # TODO we need deleting COG TileServer is ever deleted
            session.add(ts)
            session.flush()
            session.commit()

            _update_task_and_progress(
                status=TaskStatus.COMPLETED,
                latest_message=f"Import completed",
            )
        except Exception as _e:
            logger.exception(
                f"Raster import failed for {tapis_file},"
                f" user:{user.username}, project:{project_id})"
            )
            # Only update if not already marked as FAILED
            t = session.get(Task, task_id)
            if t.status != TaskStatus.FAILED.value:
                _update_task_and_progress(
                    status=TaskStatus.FAILED,
                    latest_message=f"Import failed: {tapis_file.path}",
                )

            # cleanup asset file (if exists)
            if cog_uuid:
                delete_assets(projectId=project_id, uuid=str(cog_uuid))

            # We intentionally don't re-raise (Celery will think it succeeded)
        finally:
            if tmp_file is not None:
                tmp_file.close()
