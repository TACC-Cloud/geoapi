import os
import json
import subprocess
import math
from pathlib import Path
from uuid import uuid4

from geoapi.utils.assets import make_project_asset_dir

from geoapi.celery_app import app
from geoapi.db import create_task_session
from geoapi.log import logger
from geoapi.models import Task, TaskStatus, TileServer, User
from geoapi.schema.tapis import TapisFilePath
from geoapi.utils.external_apis import TapisUtils, TapisFileGetError
from geoapi.tasks.utils import send_progress_update

ASSETS_DIR = Path(os.getenv("ASSETS_BASE_DIR", "/assets")).resolve()


def _validate_raster_name(name: str) -> None:
    ok = (".tif", ".tiff", ".geotiff")
    if not name.lower().endswith(ok):
        raise ValueError(
            f"Unsupported raster extension for '{name}'. Expected one of {ok}"
        )


def gdal_cogify(src: Path, dst: Path) -> None:
    """Convert to COG"""
    # When creating cog, we convert to Web Mercator + GoogleMapsCompatible
    # for optimal TiTiler performance
    cmd = [
        "gdalwarp",
        "-of",
        "COG",
        "-t_srs",
        "EPSG:3857",  #  Web Mercator
        "-co",
        "COMPRESS=DEFLATE",
        "-co",
        "BLOCKSIZE=512",
        "-co",
        "TILING_SCHEME=GoogleMapsCompatible",
        str(src),
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def get_cog_metadata(path: Path) -> dict:
    """Extract useful metadata from a COG for tileOptions."""
    result = subprocess.run(
        ["gdalinfo", "-json", str(path)], capture_output=True, text=True, check=True
    )
    info = json.loads(result.stdout)

    # Get the polygon from wgs84Extent
    polygon = info.get("wgs84Extent", {}).get("coordinates", [[]])[0]

    # Extract min/max lat/lng from polygon
    lngs = [coord[0] for coord in polygon]
    lats = [coord[1] for coord in polygon]

    # Convert to Leaflet bounds format: [[south, west], [north, east]]
    bounds = [[min(lats), min(lngs)], [max(lats), max(lngs)]]

    # Calculate actual max zoom based on pixel resolution
    pixel_size = abs(info["geoTransform"][1])  # pixel width in meters (Web Mercator)
    # Web Mercator at equator: zoom 0 = 156543.03 meters/pixel
    max_zoom = math.floor(math.log2(156543.03 / pixel_size))
    max_zoom = min(max(max_zoom, 0), 24)

    return {"minZoom": 0, "maxZoom": max_zoom, "bounds": bounds}


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
                t.status = status.value  # TODO
                # t.latest_message = latest_message #  TODO
                session.add(t)
                session.commit()

                send_progress_update(
                    user, t.process_id, status.value.lower(), latest_message
                )

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
                    "visible": True,
                    "zIndex": 0,  # frontend can readjust
                    "opacity": 1,
                    "isActive": True,
                },
            )
            # TODO we need to consider deleting COG if TileServer is ever deleted; create JIRA.
            session.add(ts)
            session.flush()
            session.commit()
        except Exception as _e:
            # TODO we should probably remove asset files if existing

            logger.exception(
                f"Raster import failed for {tapis_file},"
                f" user:{user.username}, project:{project_id})"
            )
            _update_task_and_progress(
                status=TaskStatus.FAILED,
                latest_message=f"Import failed {tapis_file.path}",
            )
            raise
        finally:
            if tmp_file is not None:
                tmp_file.close()
