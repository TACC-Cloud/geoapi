import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from geoapi.settings import settings
from geoapi.tasks import published_ds_maps
from geoapi.tasks.published_ds_maps import (
    ARCHIVE_PREFIX,
    ARCHIVE_SUFFIX,
    generate_published_ds_maps_pmtiles,
)

FEATURES = [
    {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-97.7, 30.3]},
        "properties": {"feature_type": "point", "feature_id": 1},
    },
    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[-97.8, 30.2], [-97.6, 30.2], [-97.6, 30.4], [-97.8, 30.4], [-97.8, 30.2]]
            ],
        },
        "properties": {"feature_type": "cog", "feature_id": None},
    },
]
STATS = {"feature_count": 1, "cog_count": 1, "project_count": 1, "total": 2}


def _write_dummy_archive(layers, output_path, *args, **kwargs):
    with open(output_path, "wb") as f:
        f.write(b"PMTILES-DUMMY")
    return len(FEATURES)  # tippecanoe "wrote" 2 features


class _ContextManagerMock:
    def __enter__(self):
        return MagicMock()

    def __exit__(self, *exc):
        return False


def _patchers(
    isolated_assets_dir,
    published_maps=("sentinel",),
    build_return=(FEATURES, STATS),
    tile_side_effect=_write_dummy_archive,
    lock_acquired=True,
):
    """Common patch set. Returns a list of started patchers (caller stops them)."""
    lock = MagicMock()
    lock.acquire.return_value = lock_acquired
    redis_client = MagicMock()
    redis_client.lock.return_value = lock

    patchers = [
        patch.object(settings, "ASSETS_BASE_DIR", isolated_assets_dir),
        patch.object(published_ds_maps.redis, "Redis", return_value=redis_client),
        patch.object(
            published_ds_maps, "create_task_session", return_value=_ContextManagerMock()
        ),
        patch.object(
            published_ds_maps.PublishedMapsService,
            "get_published_maps",
            return_value=list(published_maps),
        ),
        patch.object(
            published_ds_maps.PublishedMapsExportService,
            "build_features",
            return_value=build_return,
        ),
        patch.object(
            published_ds_maps.TippecanoeService,
            "geojson_layers_to_pmtiles",
            side_effect=tile_side_effect,
        ),
    ]
    return patchers, redis_client


def _run(patchers):
    for p in patchers:
        p.start()
    try:
        return generate_published_ds_maps_pmtiles()
    finally:
        for p in reversed(patchers):
            p.stop()


def test_generate_writes_archive_and_manifest(tmp_path):
    assets_dir = str(tmp_path)
    patchers, _ = _patchers(assets_dir)
    _run(patchers)

    public_dir = os.path.join(assets_dir, "public")
    archives = [
        n
        for n in os.listdir(public_dir)
        if n.startswith(ARCHIVE_PREFIX) and n.endswith(ARCHIVE_SUFFIX)
    ]
    assert len(archives) == 1
    filename = archives[0]

    with open(os.path.join(public_dir, "manifest.json")) as f:
        manifest = json.load(f)
    assert manifest["feature_count"] == 2
    assert manifest["project_count"] == 1
    assert manifest["zoom_min"] == 6
    assert manifest["zoom_max"] == 16
    assert manifest["schema_version"] == 1
    assert manifest["url"].endswith(f"/assets/public/{filename}")
    assert len(manifest["bounds"]) == 4
    # bounds span both features
    assert manifest["bounds"][0] == pytest.approx(-97.8)
    assert manifest["bounds"][2] == pytest.approx(-97.6)


def test_generate_skips_when_no_published_maps(tmp_path):
    assets_dir = str(tmp_path)
    patchers, _ = _patchers(assets_dir, published_maps=())
    _run(patchers)

    # nothing written, no manifest
    assert not os.path.exists(os.path.join(assets_dir, "public", "manifest.json"))


def test_generate_skips_when_lock_held(tmp_path):
    assets_dir = str(tmp_path)
    patchers, _ = _patchers(assets_dir, lock_acquired=False)
    # build_features must not be called if the lock isn't acquired
    with patch.object(
        published_ds_maps.PublishedMapsExportService, "build_features"
    ) as build:
        for p in patchers:
            p.start()
        try:
            generate_published_ds_maps_pmtiles()
        finally:
            for p in reversed(patchers):
                p.stop()
    build.assert_not_called()


def test_generate_aborts_on_count_mismatch_without_touching_manifest(tmp_path):
    assets_dir = str(tmp_path)

    def _wrong_count(layers, output_path, *a, **k):
        with open(output_path, "wb") as f:
            f.write(b"PMTILES-DUMMY")
        return 1  # fewer than the 2 we handed it -> silent drop

    patchers, _ = _patchers(assets_dir, tile_side_effect=_wrong_count)
    with pytest.raises(RuntimeError, match="feature count mismatch"):
        _run(patchers)

    # no archive placed, no manifest written
    public_dir = os.path.join(assets_dir, "public")
    assert not os.path.exists(os.path.join(public_dir, "manifest.json"))
    placed = [
        n
        for n in os.listdir(public_dir)
        if n.startswith(ARCHIVE_PREFIX) and n.endswith(ARCHIVE_SUFFIX)
    ]
    assert placed == []


def test_enqueue_generation_if_missing_enqueues_only_when_absent():
    with patch.object(published_ds_maps, "read_manifest", return_value={"url": "x"}), patch.object(
        published_ds_maps.generate_published_ds_maps_pmtiles, "delay"
    ) as delay:
        assert published_ds_maps.enqueue_generation_if_missing() is False
        delay.assert_not_called()

    with patch.object(published_ds_maps, "read_manifest", return_value=None), patch.object(
        published_ds_maps.generate_published_ds_maps_pmtiles, "delay"
    ) as delay:
        assert published_ds_maps.enqueue_generation_if_missing() is True
        delay.assert_called_once()


def test_generate_prunes_old_archives_but_keeps_recent(tmp_path):
    assets_dir = str(tmp_path)
    public_dir = os.path.join(assets_dir, "public")
    os.makedirs(public_dir, exist_ok=True)

    old = os.path.join(public_dir, f"{ARCHIVE_PREFIX}20200101T000000Z{ARCHIVE_SUFFIX}")
    recent = os.path.join(public_dir, f"{ARCHIVE_PREFIX}20990101T000000Z{ARCHIVE_SUFFIX}")
    for path in (old, recent):
        with open(path, "wb") as f:
            f.write(b"old")
    # make `old` older than the 26h window; leave `recent` fresh
    stale = time.time() - (30 * 3600)
    os.utime(old, (stale, stale))

    patchers, _ = _patchers(assets_dir)
    _run(patchers)

    remaining = set(os.listdir(public_dir))
    assert os.path.basename(old) not in remaining  # pruned (stale)
    assert os.path.basename(recent) in remaining  # kept (fresh)
    # the newly generated archive is present too
    assert any(
        n.startswith(ARCHIVE_PREFIX)
        and n.endswith(ARCHIVE_SUFFIX)
        and n not in {os.path.basename(old), os.path.basename(recent)}
        for n in remaining
    )
