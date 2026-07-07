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
