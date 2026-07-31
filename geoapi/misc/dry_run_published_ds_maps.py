"""
Non-destructive dry run of creating published DesignSafe maps archive. Useful for testing out
on prod and staging systems before deployment. See README.md
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections import Counter, defaultdict

from geoapi.custom.designsafe.published_export import PublishedMapsExportService
from geoapi.custom.designsafe.published_maps import PublishedMapsService
from geoapi.db import create_task_session
from geoapi.services.tippecanoe import (
    PUBLISHED_DS_MAPS_BASE_ZOOM,
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
    print(
        f"zoom range         : z{PUBLISHED_DS_MAPS_MIN_ZOOM}-z{PUBLISHED_DS_MAPS_MAX_ZOOM} "
        f"(all features kept at base z{PUBLISHED_DS_MAPS_BASE_ZOOM}+)"
    )
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
        features, layer_features, stats = PublishedMapsExportService.build_features(
            session, published
        )

    print(f"Tiled features     : {stats['feature_count']}")
    print(
        f"Layer footprints   : {stats['cog_count']} COG + {stats['vector_count']} "
        "vector (companion geojson)"
    )

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

    bounds = _bounds(features + layer_features)
    print(f"\nBounds [minx,miny,maxx,maxy]: {bounds}")

    # tile into a scratch path (NOT the real public area). Layer footprints (COGs +
    # vectors) are not tiled -- they go to a companion geojson (see below).
    archive_path = args.out or os.path.join(
        str(get_temp_dir()), "published_ds_maps.pmtiles"
    )
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)
    work_dir = tempfile.mkdtemp(prefix="layers_", dir=os.path.dirname(archive_path))
    written_total = 0
    try:
        layer_files = _write_layer_files(features, work_dir)
        print("\nPer-layer tiling (feature count / time / size):")
        per_layer_pmtiles = []
        for layer_name, geojson_path in layer_files:
            layer_pmtiles = os.path.join(work_dir, f"{layer_name}.pmtiles")
            start = time.time()
            count = TippecanoeService.geojson_layers_to_pmtiles(
                [(layer_name, geojson_path)], layer_pmtiles
            )
            elapsed = time.time() - start
            written_total += count or 0
            per_layer_pmtiles.append(layer_pmtiles)
            print(
                f"  {layer_name:<14} {count or 0:>7} feat  {elapsed:>8.1f}s  "
                f"{_human_bytes(os.path.getsize(layer_pmtiles))}"
            )

        print(f"\nCombining {len(per_layer_pmtiles)} layer(s) -> {archive_path} ...")
        subprocess.run(
            ["tile-join", "--force", "--no-tile-size-limit", "-o", archive_path]
            + per_layer_pmtiles,
            check=True,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    # companion layer footprints (COGs + vectors), rendered client-side, not tiled
    layers_path = (
        os.path.splitext(archive_path)[0] + ".vectors_and_internal_cogs.geojson"
    )
    with open(layers_path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": layer_features}, f)
    layers_size = os.path.getsize(layers_path)

    archive_size = os.path.getsize(archive_path)
    print("-" * 72)
    print(f"features tiled     : {written_total} (source had {stats['feature_count']})")
    if written_total != stats["feature_count"]:
        print("  WARNING: count mismatch -- features were dropped!")
    print(f"ARCHIVE SIZE       : {_human_bytes(archive_size)} ({archive_size} bytes)")
    print(
        f"layers geojson     : {_human_bytes(layers_size)} "
        f"({stats['cog_count']} COG + {stats['vector_count']} vector)"
    )
    print(f"Archive path       : {archive_path}")
    print(f"Layers path        : {layers_path}")
    print(
        f"\n(Delete {archive_path} and {layers_path} when done. Nothing was written "
        "to the real assets/public area or manifest.)"
    )


if __name__ == "__main__":
    main()
