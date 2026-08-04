import os
import re
import shutil
import subprocess
import tempfile
from unittest.mock import patch

import pytest

from geoapi.services.tippecanoe import TippecanoeService


def _completed(returncode=0, stderr=""):
    class _Result:
        pass

    result = _Result()
    result.returncode = returncode
    result.stderr = stderr
    result.stdout = ""
    return result


def test_geojson_to_pmtiles_builds_expected_command():
    with patch("geoapi.services.tippecanoe.subprocess.run") as mock_run:
        mock_run.return_value = _completed()
        out = TippecanoeService.geojson_to_pmtiles(
            "/tmp/in.geojson", "/tmp/out.pmtiles", "my_layer"
        )

    assert out == "/tmp/out.pmtiles"
    cmd = mock_run.call_args[0][0]
    # output, force, layer, density management, guessed zoom, and input file
    assert cmd[0] == "tippecanoe"
    assert "-o" in cmd and cmd[cmd.index("-o") + 1] == "/tmp/out.pmtiles"
    assert "--force" in cmd
    assert "-l" in cmd and cmd[cmd.index("-l") + 1] == "my_layer"
    assert "--drop-densest-as-needed" in cmd
    assert "-zg" in cmd
    # the guessed max zoom is floored so sparse global data still renders
    assert "--smallest-maximum-zoom-guess=12" in cmd
    assert cmd[-1] == "/tmp/in.geojson"
    # parallel read is opt-in
    assert "-P" not in cmd


def test_geojson_to_pmtiles_missing_binary_raises_runtimeerror():
    with patch(
        "geoapi.services.tippecanoe.subprocess.run", side_effect=FileNotFoundError()
    ):
        with pytest.raises(RuntimeError, match="tippecanoe binary not found"):
            TippecanoeService.geojson_to_pmtiles(
                "/tmp/in.geojson", "/tmp/out.pmtiles", "layer"
            )


def test_geojson_to_pmtiles_nonzero_exit_raises_runtimeerror():
    with patch("geoapi.services.tippecanoe.subprocess.run") as mock_run:
        mock_run.return_value = _completed(returncode=1, stderr="boom")
        with pytest.raises(RuntimeError, match="exit code 1"):
            TippecanoeService.geojson_to_pmtiles(
                "/tmp/in.geojson", "/tmp/out.pmtiles", "layer"
            )


def _point_counts_by_zoom(pmtiles_path):
    """Decode a .pmtiles and return {zoom: number of point features}."""
    decoded = subprocess.run(
        ["tippecanoe-decode", pmtiles_path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    counts = {}
    zoom = None
    for line in decoded.splitlines():
        m = re.search(r'"zoom": (\d+)', line)
        if m:
            zoom = int(m.group(1))
        if '"Point"' in line and zoom is not None:
            counts[zoom] = counts.get(zoom, 0) + line.count('"Point"')
    return counts


def test_geojson_layers_to_pmtiles_builds_command():
    with patch("geoapi.services.tippecanoe.subprocess.run") as mock_run:
        mock_run.return_value = _completed(stderr="42 features, 1234 bytes of geometry")
        count = TippecanoeService.geojson_layers_to_pmtiles(
            [("points", "/tmp/points.geojson"), ("cog", "/tmp/cog.geojson")],
            "/tmp/out.pmtiles",
        )

    # the feature count is parsed from tippecanoe's summary line
    assert count == 42
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "tippecanoe"
    assert "-o" in cmd and cmd[cmd.index("-o") + 1] == "/tmp/out.pmtiles"
    assert cmd[cmd.index("-Z") + 1] == "2"
    assert cmd[cmd.index("-z") + 1] == "14"
    assert cmd[cmd.index("-B") + 1] == "8"
    assert "--drop-densest-as-needed" in cmd
    assert "--no-tile-size-limit" not in cmd
    assert "--no-feature-limit" in cmd
    assert "--no-tiny-polygon-reduction" in cmd
    assert "--drop-rate=1" not in cmd
    assert "points:/tmp/points.geojson" in cmd
    assert "cog:/tmp/cog.geojson" in cmd


def test_geojson_layers_to_pmtiles_requires_layers():
    with pytest.raises(ValueError, match="at least one layer"):
        TippecanoeService.geojson_layers_to_pmtiles([], "/tmp/out.pmtiles")


def test_parse_written_feature_count_ignores_progress_line():
    stderr = "Read 0.00 million features\n7 features, 10 bytes of geometry\n"
    assert TippecanoeService._parse_written_feature_count(stderr) == 7
    assert TippecanoeService._parse_written_feature_count("no summary here") is None


@pytest.mark.worker
def test_geojson_layers_to_pmtiles_multilayer():
    # tile a point layer and a polygon (COG-footprint-like) layer into one
    # archive; assert the reported count matches input and both layers survive.
    out_dir = tempfile.mkdtemp(prefix="geoapi_published_ds_maps_test_")
    try:
        points_path = os.path.join(out_dir, "points.geojson")
        shapes_path = os.path.join(out_dir, "shapes.geojson")
        with open(points_path, "w") as f:
            f.write(
                '{"type":"Feature","geometry":{"type":"Point",'
                '"coordinates":[-97.7,30.3]},"properties":{"feature_type":"point"}}\n'
            )
        with open(shapes_path, "w") as f:
            f.write(
                '{"type":"Feature","geometry":{"type":"Polygon","coordinates":'
                "[[[-97.8,30.2],[-97.6,30.2],[-97.6,30.4],[-97.8,30.4],[-97.8,30.2]]]},"
                '"properties":{"feature_type":"cog"}}\n'
            )

        pmtiles_path = os.path.join(out_dir, "out.pmtiles")
        count = TippecanoeService.geojson_layers_to_pmtiles(
            [("points", points_path), ("cogs", shapes_path)], pmtiles_path
        )

        assert os.path.isfile(pmtiles_path)
        assert count == 2  # both input features present, none dropped

        decoded = subprocess.run(
            ["tippecanoe-decode", pmtiles_path],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert '"points"' in decoded
        assert '"cogs"' in decoded
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


@pytest.mark.worker
def test_geojson_to_pmtiles_keeps_features_at_all_zooms(
    points_1000_geojson_path_fixture,
):
    # tippecanoe drops features at low zoom by default, which would leave a
    # scattered point layer nearly empty at the world view. --drop-rate=1 keeps
    # every feature at every zoom; assert almost all 1000 points survive at each
    # zoom, including the outermost (z0).
    out_dir = tempfile.mkdtemp(prefix="geoapi_pmtiles_zoom_test_")
    try:
        pmtiles_path = os.path.join(out_dir, "out.pmtiles")
        TippecanoeService.geojson_to_pmtiles(
            points_1000_geojson_path_fixture, pmtiles_path, "pts"
        )
        counts = _point_counts_by_zoom(pmtiles_path)

        assert counts, "no point features decoded from the archive"
        assert 0 in counts, "archive has no world-view (zoom 0) tile"
        for zoom, n in sorted(counts.items()):
            assert n > 900, f"zoom {zoom} kept only {n} points (features dropped)"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
