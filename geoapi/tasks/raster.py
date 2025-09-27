import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from celery import current_task

from geoapi.celery_app import app
from geoapi.db import create_task_session
from geoapi.log import logger
from geoapi.models import Task, TileServer, User
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
    return f"file://{p}"


def _gdal_cogify(src: Path, dst: Path) -> None:
    _ensure_dir(dst.parent)
    # TODO check and confirm these are best for TiTiler and our use case
    cmd = [
        "gdal_translate",
        "-of",
        "COG",
        "-co",
        "COMPRESS=DEFLATE",
        "-co",
        "PREDICTOR=2",
        "-co",
        "ZLEVEL=9",
        "-co",
        "BLOCKSIZE=512",
        "-co",
        "NUM_THREADS=ALL_CPUS",
        "-co",
        "BIGTIFF=IF_SAFER",
        "-co",
        "TILING_SCHEME=GoogleMapsCompatible",
        str(src),
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def _is_cog(path: Path) -> bool:
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
    userId: int,
    files: list[dict],
    projectId: int,
    taskId: int,
) -> dict:
    """
    Download rasters from Tapis (system/path), store under:
        /assets/{projectId}/{uuid}/
    If already a COG -> store as-is ( copy as `data.cog.tif`).
    If not a COG -> convert to COG as {uuid}/data.cog.tif
    Then register a TileServer pointing to TiTiler.

    Returns:
        {"tile_server_ids": [int, ...]}
    """
    created_tile_server_ids: list[int] = []
    with create_task_session() as session:

        def _set_task(status: str, desc: str | None = None) -> None:
            t = session.get(Task, taskId)
            if not t:
                return
            t.status = status
            if desc:
                t.description = desc
            t.updated = datetime.utcnow()
            session.add(t)
            session.commit()

        try:
            task_uuid = current_task.request.id
        except Exception:
            task_uuid = None

        try:
            user = session.get(User, userId)
            client = TapisUtils(session, user)

            _set_task("RUNNING", f"Importing {len(files)} raster file(s)")
            if task_uuid:
                send_progress_update(
                    user, task_uuid, "success", "Starting raster import"
                )

            for idx, f in enumerate(files, start=1):
                system = f["system"]
                rpath = f["path"]
                src_name = Path(rpath).name
                _validate_raster_name(src_name)

                if task_uuid:
                    send_progress_update(
                        user,
                        task_uuid,
                        "success",
                        f"[{idx}/{len(files)}] Fetching {system}:{rpath}",
                    )

                # Download file
                try:
                    tmp_file = client.getFile(system, rpath)  # temp file-like
                except TapisFileGetError:
                    logger.exception("Tapis getFile failed for %s:%s", system, rpath)
                    _set_task("FAILED", f"Unable to download {system}:{rpath}")
                    if task_uuid:
                        send_progress_update(
                            user,
                            task_uuid,
                            "error",
                            f"Download failed: {system}:{rpath}",
                        )
                    raise

                tmp_file.filename = src_name
                with tempfile.TemporaryDirectory() as td:
                    local_src = Path(td) / src_name
                    with open(local_src, "wb") as outfp:
                        outfp.write(tmp_file.read())
                    tmp_file.close()

                    # Choose UUID folder and layout
                    asset_uuid = uuid4()
                    asset_dir = (
                        ASSETS_DIR / str(projectId) / str(asset_uuid)
                    ).resolve()
                    _ensure_dir(asset_dir)

                    cog_path = asset_dir / "data.cog.tif"

                    if _is_cog(local_src):
                        # If already a COG, store it directly
                        cog_path.write_bytes(local_src.read_bytes())
                        status_note = " (already COG)"
                    else:
                        # Build a COG
                        if task_uuid:
                            send_progress_update(
                                user,
                                task_uuid,
                                "success",
                                f"[{idx}/{len(files)}] Converting to COG",
                            )
                        _gdal_cogify(local_src, cog_path)
                        status_note = ""

                # Create TileServer pointing to TiTiler
                file_url = _file_url_for_titiler(cog_path)
                ts = TileServer(
                    project_id=projectId,
                    name=f"Raster {asset_uuid}",
                    type="xyz",
                    url=f"/tiles/cog/tiles/{{z}}/{{x}}/{{y}}.png?url={file_url}",
                    attribution="",
                    tileOptions={"minZoom": 0, "maxZoom": 22},
                    uiOptions={
                        "group": "COGs",
                        "visible": True,
                        "uuid": str(asset_uuid),
                    },
                )
                # TODO we need to consider deleting COG if TileServer is ever deleted; follow on JIRA.
                session.add(ts)
                session.flush()
                created_tile_server_ids.append(ts.id)

                if task_uuid:
                    send_progress_update(
                        user,
                        task_uuid,
                        "success",
                        f"[{idx}/{len(files)}] Registered {asset_uuid}{status_note}",
                    )

            _set_task("SUCCESS", f"Imported {len(created_tile_server_ids)} raster(s)")
            if task_uuid:
                send_progress_update(
                    user,
                    task_uuid,
                    "success",
                    f"Completed: {len(created_tile_server_ids)} raster(s)",
                )
            session.commit()
            return {"tile_server_ids": created_tile_server_ids}

        except Exception as e:
            logger.exception("Raster import failed for project:%s", projectId)
            session.rollback()
            _set_task("FAILED", f"Import failed: {e}")
            try:
                user = session.get(User, userId)
                if task_uuid:
                    send_progress_update(
                        user, task_uuid, "error", f"Import failed: {e}"
                    )
            except Exception:
                pass
            raise
