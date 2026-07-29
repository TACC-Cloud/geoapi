"""
Non-destructive dry run of the WG-703 published DesignSafe maps archive.

Runs the REAL selector + exporter + tiler against whatever database the
environment is configured for, tiles into a scratch directory, and prints
counts, a per-layer breakdown, per-feature property-size stats, bounds, and the
total archive size. Use it to answer "how big is this archive and how many
projects/features?" before deploying -- e.g. pointed at production data.

It is safe to run against production:
  * DB access is READ-ONLY (SELECT via the ORM; nothing is written to the DB).
  * Output goes ONLY to a scratch dir -- it never touches the real
    assets/public area or manifest.json.
  * It does NOT take the generation lock and does NOT enqueue anything.

Requirements: this must run from a geoapi-workers image (it has tippecanoe + this
code) with the environment pointed at the target DB. APP_ENV must match the tier
whose maps you want (production maps are tagged deployment=production), because
the selector filters on `deployment == APP_ENV` and the URLs baked into the
archive come from APP_ENV.

See misc/README.md for how to run it (local + production) and what it reports.
"""

import argparse
import json
import os
import shutil
import tempfile
from collections import Counter, defaultdict

from geoapi.custom.designsafe.published_export import PublishedMapsExportService
from geoapi.custom.designsafe.published_maps import PublishedMapsService
from geoapi.db import create_task_session
from geoapi.services.tippecanoe import (
    PUBLISHED_DS_MAPS_MAX_ZOOM,
    PUBLISHED_DS_MAPS_MIN_ZOOM,
    TippecanoeService,
)
from geoapi.settings import settings
from geoapi.tasks.published_ds_maps import _bounds, _write_layer_files
from geoapi.utils.assets import get_temp_dir
from geoapi.utils.client_backend import (
    get_deployed_geoapi_url,
    get_deployed_hazmapper_url,
)


def _human_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}"
        n /= 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=None,
        help="output .pmtiles path (default: "
        "/assets/tmp/published_ds_maps.pmtiles; never the real assets/public area)",
    )
    args = parser.parse_args()

    print("=" * 72)
    print("WG-703 published DesignSafe maps archive -- DRY RUN (non-destructive)")
    print("=" * 72)
    print(f"APP_ENV            : {settings.APP_ENV}")
    print(f"DB host / name     : {settings.DB_HOST} / {settings.DB_NAME}")
    print(f"geoapi base URL    : {get_deployed_geoapi_url()}")
    print(f"hazmapper base URL : {get_deployed_hazmapper_url()}")
    print(f"zoom range         : z{PUBLISHED_DS_MAPS_MIN_ZOOM}-z{PUBLISHED_DS_MAPS_MAX_ZOOM}")
    print("-" * 72)

    with create_task_session() as session:
        published = PublishedMapsService.get_published_maps(session)
        print(f"Published, public maps for this deployment: {len(published)}")
        if not published:
            print(
                "\nNothing to measure. If you expected results, check that APP_ENV "
                "matches the maps' deployment tag and that the DB is the right tier."
            )
            return
        features, stats = PublishedMapsExportService.build_features(session, published)

    print(f"DB features        : {stats['feature_count']}")
    print(f"COG footprints     : {stats['cog_count']}")
    print(f"Total features     : {stats['total']}")

    # per-layer (feature_type) breakdown
    by_type = Counter(f["properties"].get("feature_type") for f in features)
    print("\nPer-layer (feature_type) counts:")
    for feature_type, count in by_type.most_common():
        print(f"  {feature_type:<14} {count}")

    # per-feature property payload analysis (informs the projects.json decision)
    total_props_bytes = 0
    per_key_bytes = defaultdict(int)
    for f in features:
        props = f["properties"]
        total_props_bytes += len(json.dumps(props))
        for key, value in props.items():
            per_key_bytes[key] += len(json.dumps({key: value}))
    avg_props = total_props_bytes / len(features) if features else 0
    print(
        f"\nProperty payload   : {_human_bytes(total_props_bytes)} total, "
        f"{avg_props:.0f} bytes/feature avg (pre-tiling, uncompressed)"
    )
    print("Heaviest property keys (total bytes across all features):")
    for key, nbytes in sorted(per_key_bytes.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {key:<16} {_human_bytes(nbytes)}")

    bounds = _bounds(features)
    print(f"\nBounds [minx,miny,maxx,maxy]: {bounds}")

    # tile into a scratch path (NOT the real public area)
    archive_path = args.out or os.path.join(
        str(get_temp_dir()), "published_ds_maps.pmtiles"
    )
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)
    work_dir = tempfile.mkdtemp(prefix="layers_", dir=os.path.dirname(archive_path))
    try:
        layer_files = _write_layer_files(features, work_dir)
        print(f"\nTiling {len(layer_files)} layer(s) into {archive_path} ...")
        written = TippecanoeService.geojson_layers_to_pmtiles(layer_files, archive_path)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    archive_size = os.path.getsize(archive_path)
    print("-" * 72)
    print(f"tippecanoe wrote   : {written} features (source had {stats['total']})")
    if written != stats["total"]:
        print("  WARNING: count mismatch -- features were dropped!")
    print(f"ARCHIVE SIZE       : {_human_bytes(archive_size)} ({archive_size} bytes)")
    print(f"Archive path       : {archive_path}")
    print(
        f"\n(Delete {archive_path} when done. Nothing was written to the real "
        "assets/public area or manifest.)"
    )


if __name__ == "__main__":
    main()
