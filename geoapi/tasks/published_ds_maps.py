import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import redis
import shapely.geometry

from geoapi.celery_app import app
from geoapi.custom.designsafe.published_export import PublishedMapsExportService
from geoapi.custom.designsafe.published_maps import PublishedMapsService
from geoapi.db import create_task_session
from geoapi.log import logger
from geoapi.services.tippecanoe import (
    PUBLISHED_DS_MAPS_MAX_ZOOM,
    PUBLISHED_DS_MAPS_MIN_ZOOM,
    TippecanoeService,
)
from geoapi.settings import settings
from geoapi.utils.assets import get_temp_dir
from geoapi.utils.client_backend import get_deployed_geoapi_url

# Layout of the shared public asset area (served unauthenticated by nginx).
PUBLIC_ASSET_SUBDIR = "public"
MANIFEST_FILENAME = "manifest.json"

# Versioned, lexicographically-sortable archive name:
#   published_ds_maps_20260724T030000Z.pmtiles
ARCHIVE_PREFIX = "published_ds_maps_"
ARCHIVE_SUFFIX = ".pmtiles"

# Bumped when the manifest/property schema changes in a way consumers must notice.
SCHEMA_VERSION = 1

# Prune archives older than this, but never the one the manifest references. 26h
# (not 24h) leaves margin for a late run so a predecessor isn't removed early; in
# steady state this keeps two generations.
PRUNE_AGE_SECONDS = 26 * 3600

# Redis lock so a nightly beat, a startup enqueue, and a manual trigger can't run
# two tippecanoe builds at once. Auto-expires so a crashed run doesn't wedge it.
GENERATION_LOCK_KEY = "published_ds_maps:generation"
GENERATION_LOCK_TIMEOUT_SECONDS = 2 * 3600


def public_asset_dir() -> str:
    return os.path.join(settings.ASSETS_BASE_DIR, PUBLIC_ASSET_SUBDIR)


def manifest_path() -> str:
    return os.path.join(public_asset_dir(), MANIFEST_FILENAME)


def read_manifest() -> Optional[dict]:
    """Return the current manifest dict, or None if there isn't one yet."""
    try:
        with open(manifest_path()) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return None


def _public_asset_url(filename: str) -> str:
    return f"{get_deployed_geoapi_url()}/assets/{PUBLIC_ASSET_SUBDIR}/{filename}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _archive_filename(now: datetime) -> str:
    # UTC, explicit Z, no colons/spaces -> filesystem- and URL-safe and sortable
    return f"{ARCHIVE_PREFIX}{now.strftime('%Y%m%dT%H%M%SZ')}{ARCHIVE_SUFFIX}"


def _write_layer_files(features: List[dict], work_dir: str) -> List[Tuple[str, str]]:
    """Write features grouped by ``feature_type`` to newline-delimited GeoJSON.

    :return: list of ``(layer_name, file_path)`` for tippecanoe named layers
    """
    grouped: dict = {}
    for feature in features:
        layer = feature["properties"].get("feature_type") or "feature"
        grouped.setdefault(layer, []).append(feature)

    layer_files: List[Tuple[str, str]] = []
    for layer, layer_features in grouped.items():
        path = os.path.join(work_dir, f"{layer}.geojson")
        with open(path, "w") as f:
            for feature in layer_features:
                f.write(json.dumps(feature))
                f.write("\n")
        layer_files.append((layer, path))
    return layer_files


def _bounds(features: List[dict]) -> Optional[List[float]]:
    """[minx, miny, maxx, maxy] over all feature geometries (lon/lat)."""
    minx = miny = maxx = maxy = None
    for feature in features:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        fminx, fminy, fmaxx, fmaxy = shapely.geometry.shape(geometry).bounds
        minx = fminx if minx is None else min(minx, fminx)
        miny = fminy if miny is None else min(miny, fminy)
        maxx = fmaxx if maxx is None else max(maxx, fmaxx)
        maxy = fmaxy if maxy is None else max(maxy, fmaxy)
    if minx is None:
        return None
    return [minx, miny, maxx, maxy]


def _verify_feature_count(source_count: int, written_count: Optional[int]) -> None:
    """Guard against silent dropping (the main failure mode of tiling).

    Raises if tippecanoe wrote fewer features than we handed it, so the caller
    aborts before overwriting a good archive/manifest.
    """
    if written_count is None:
        logger.warning(
            "Could not parse tippecanoe's feature count; skipping the "
            "source-vs-archive count check (expected %s).",
            source_count,
        )
        return
    if written_count != source_count:
        raise RuntimeError(
            "Public archive feature count mismatch: handed tippecanoe "
            f"{source_count} feature(s) but it wrote {written_count}. Features "
            "were dropped -- aborting without touching the existing archive."
        )
    logger.info("Public archive feature count verified: %s.", source_count)


def _prune_old_archives(keep_filename: str) -> None:
    """Delete archives older than PRUNE_AGE_SECONDS, never the referenced one."""
    directory = public_asset_dir()
    manifest = read_manifest() or {}
    referenced = os.path.basename(manifest.get("url", "")) if manifest else ""
    now = time.time()
    for name in os.listdir(directory):
        if not (name.startswith(ARCHIVE_PREFIX) and name.endswith(ARCHIVE_SUFFIX)):
            continue
        if name == keep_filename or name == referenced:
            continue
        path = os.path.join(directory, name)
        try:
            age = now - os.path.getmtime(path)
        except OSError:
            continue
        if age > PRUNE_AGE_SECONDS:
            try:
                os.remove(path)
                logger.info(
                    "Pruned stale public archive %s (age %.1fh).", name, age / 3600
                )
            except OSError:
                logger.exception("Failed to prune public archive %s.", name)


@app.task(queue="heavy")
def generate_published_ds_maps_pmtiles():
    """Nightly: build the combined public PMTiles archive for published DS maps.

    Selects this deployment's published, public maps, exports their features
    (plus internal-COG footprints) to GeoJSON, tiles them with no dropping, and
    atomically publishes the archive + a sidecar manifest into the shared public
    asset area. Fails loudly and leaves the previous archive/manifest untouched
    on any error. Guarded by a Redis lock so runs can't overlap.

    Runs nightly via celery beat; on a fresh environment app startup also enqueues
    one build if no manifest exists yet (see on_startup in app.py). To regenerate
    manually (the Redis lock keeps it from colliding with the nightly):

        # enqueue onto the heavy worker (returns immediately)
        docker exec -it geoapi_workers python -c \
          "from geoapi.tasks.published_ds_maps import \
           generate_published_ds_maps_pmtiles as t; t.delay()"

        # or run synchronously (blocks until the archive is built)
        docker exec -it geoapi_workers python -c \
          "from geoapi.tasks.published_ds_maps import \
           generate_published_ds_maps_pmtiles as t; t.apply()"

    For a non-destructive dry run that only measures counts/size, see
    geoapi/misc/dry_run_published_ds_maps.py.
    """
    start_time = time.time()
    redis_client = redis.Redis(
        host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0
    )
    lock = redis_client.lock(
        GENERATION_LOCK_KEY, timeout=GENERATION_LOCK_TIMEOUT_SECONDS
    )
    if not lock.acquire(blocking=False):
        logger.info(
            "Public pmtiles generation is already running; skipping this trigger."
        )
        return

    try:
        with create_task_session() as session:
            published_maps = PublishedMapsService.get_published_maps(session)
            if not published_maps:
                logger.info(
                    "No published maps for deployment '%s'; leaving any existing "
                    "archive and manifest untouched.",
                    settings.APP_ENV,
                )
                return
            features, stats = PublishedMapsExportService.build_features(
                session, published_maps
            )

        if not features:
            logger.info(
                "Published maps yielded no features; leaving any existing archive "
                "and manifest untouched."
            )
            return

        os.makedirs(public_asset_dir(), exist_ok=True)
        # Work under ASSETS_BASE_DIR/tmp so the finished archive is on the SAME
        # filesystem as the public dir and os.replace() is atomic.
        work_dir = tempfile.mkdtemp(prefix="published_ds_maps_", dir=str(get_temp_dir()))
        now = _utc_now()
        filename = _archive_filename(now)
        try:
            layer_files = _write_layer_files(features, work_dir)
            staged_archive = os.path.join(work_dir, filename)
            written_count = TippecanoeService.geojson_layers_to_pmtiles(
                layer_files, staged_archive
            )
            _verify_feature_count(len(features), written_count)

            final_archive = os.path.join(public_asset_dir(), filename)
            # atomic within the same filesystem: a partial archive is never readable
            os.replace(staged_archive, final_archive)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        manifest = {
            "url": _public_asset_url(filename),
            "generated_at": now.isoformat(),
            "feature_count": stats["total"],
            "project_count": stats["project_count"],
            "bounds": _bounds(features),
            "zoom_min": PUBLISHED_DS_MAPS_MIN_ZOOM,
            "zoom_max": PUBLISHED_DS_MAPS_MAX_ZOOM,
            "schema_version": SCHEMA_VERSION,
        }
        _write_manifest(manifest)

        # prune only after the manifest points at the new archive
        _prune_old_archives(keep_filename=filename)

        logger.info(
            "Public pmtiles archive published: %s (%s features across %s projects) "
            "in %.1fs.",
            filename,
            stats["total"],
            stats["project_count"],
            time.time() - start_time,
        )
    except Exception:
        logger.exception(
            "Failed to generate public pmtiles archive; previous archive and "
            "manifest left untouched."
        )
        raise
    finally:
        try:
            lock.release()
        except Exception:  # noqa: E722
            # lock may have already expired; nothing actionable
            pass


def _write_manifest(manifest: dict) -> None:
    """Atomically replace the sidecar manifest.json."""
    tmp_path = manifest_path() + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(manifest, f)
    os.replace(tmp_path, manifest_path())


def enqueue_generation_if_missing() -> bool:
    """Cold-start self-heal: enqueue a build if no manifest exists yet.

    Called on app startup so a fresh environment produces an archive within one
    task run instead of waiting for the nightly beat. Never runs generation
    inline (that would block the worker for minutes); the Redis lock keeps this
    from overlapping the nightly or a manual trigger.

    :return: True if a generation task was enqueued
    """
    if read_manifest() is not None:
        return False
    try:
        generate_published_ds_maps_pmtiles.delay()
        logger.info("No public pmtiles manifest present; enqueued initial generation.")
        return True
    except Exception:
        logger.exception("Failed to enqueue initial public pmtiles generation.")
        return False
