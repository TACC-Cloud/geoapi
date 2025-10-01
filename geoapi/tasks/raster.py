import os
import subprocess
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


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _validate_raster_name(name: str) -> None:
    ok = (".tif", ".tiff", ".geotiff")
    if not name.lower().endswith(ok):
        raise ValueError(
            f"Unsupported raster extension for '{name}'. Expected one of {ok}"
        )


def _file_url_for_titiler(p: Path) -> str:
    """
    Create a properly encoded file URL for TiTiler.
    TiTiler expects: file:///path/to/file.tif
    """
    # Convert to absolute path string
    abs_path = str(p.resolve())
    # URL encode the path (but not the file:// prefix)
    return f"file://{abs_path}"

def gdal_cogify(src: Path, dst: Path) -> None:
    _ensure_dir(dst.parent)
    # TODO check and confirm these are best for TiTiler and our use case
    cmd = [
        "gdal_translate",
        "-of",
        "COG",
        # Compression settings
        "-co",
        "COMPRESS=DEFLATE",
        "-co",
        "PREDICTOR=2",
        "-co",
        "ZLEVEL=9",
        # Tiling and performance
        "-co",
        "BLOCKSIZE=512",
        "-co",
        "NUM_THREADS=ALL_CPUS",
        "-co",
        "BIGTIFF=IF_SAFER",
        str(src),
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def is_cog(path: Path) -> bool:
    """
    Detect if a GeoTIFF is a Cloud Optimized GeoTIFF by asking gdalinfo.
    Two robust checks:
      1) Plain text contains 'Cloud Optimized GeoTIFF: Yes'
      2) JSON has metadata flagging COG layout (varies by GDAL version)
    """
    try:
        # Text mode check (stable across many GDAL versions)
        proc = subprocess.run(
            ["gdalinfo", str(path)], capture_output=True, text=True, check=True
        )
        if "Cloud Optimized GeoTIFF: Yes" in proc.stdout:
            return True
        # Fallback JSON probe
        procj = subprocess.run(
            ["gdalinfo", "-json", str(path)], capture_output=True, text=True, check=True
        )
        return (
            '"Cloud Optimized GeoTIFF": "Yes"' in procj.stdout
            or '"LAYOUT": "COG"' in procj.stdout
        )
    except Exception:
        return False


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
            if is_cog(src_path):
                # If already a COG, store it directly
                cog_path.write_bytes(src_path.read_bytes())
            else:
                _update_task_and_progress(latest_message="Processing file")
                gdal_cogify(src_path, cog_path)

            # Create TileServer pointing to TiTiler
            file_url = _file_url_for_titiler(cog_path)
            ts = TileServer(
                project_id=project_id,
                name=tapis_file.path,
                type="xyz",
                kind="cog",
                internal=True,
                url=f"/tiles/cog/tiles/{{z}}/{{x}}/{{y}}.png?url={file_url}",
                attribution="",
                tileOptions={"minZoom": 0, "maxZoom": 22},
                uiOptions={
                    "visible": True,
                    "uuid": str(cog_uuid),
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
