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
    assert cmd[-1] == "/tmp/in.geojson"
    # parallel read is opt-in
    assert "-P" not in cmd


def test_geojson_to_pmtiles_explicit_zoom_and_parallel():
    with patch("geoapi.services.tippecanoe.subprocess.run") as mock_run:
        mock_run.return_value = _completed()
        TippecanoeService.geojson_to_pmtiles(
            "/tmp/in.geojson",
            "/tmp/out.pmtiles",
            "layer",
            min_zoom=2,
            max_zoom=14,
            read_parallel=True,
        )

    cmd = mock_run.call_args[0][0]
    assert "-z" in cmd and cmd[cmd.index("-z") + 1] == "14"
    assert "-Z" in cmd and cmd[cmd.index("-Z") + 1] == "2"
    assert "-P" in cmd
    # explicit max zoom replaces the auto-guess flag
    assert "-zg" not in cmd


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
