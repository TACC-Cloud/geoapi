import os
import subprocess

from geoapi.log import logging

logger = logging.getLogger(__name__)

# tippecanoe binary; overridable for environments where it is not on PATH
TIPPECANOE_BIN = os.environ.get("TIPPECANOE_BIN", "tippecanoe")


class TippecanoeService:
    """
    Utilities for converting GeoJSON into PMTiles vector tiles via tippecanoe.

    tippecanoe (https://github.com/felt/tippecanoe) is invoked as a subprocess.
    """

    @staticmethod
    def geojson_to_pmtiles(
        geojson_path: str,
        output_path: str,
        layer_name: str,
        min_zoom: int = None,
        max_zoom: int = None,
        read_parallel: bool = False,
    ) -> str:
        """
        Convert a GeoJSON file into a PMTiles archive using tippecanoe.

        :param geojson_path: path to the source GeoJSON file
        :param output_path: path where the .pmtiles archive will be written
        :param layer_name: name of the vector tile layer
        :param min_zoom: optional minimum zoom; defaults to tippecanoe's default
        :param max_zoom: optional maximum zoom; when omitted, tippecanoe guesses
            an appropriate maximum zoom via ``-zg``
        :param read_parallel: read the input in parallel (``-P``); only valid for
            line-delimited GeoJSON input, so disabled by default
        :return: output_path
        :raises RuntimeError: if the tippecanoe binary is missing or exits non-zero
        """
        cmd = [
            TIPPECANOE_BIN,
            "-o",
            output_path,
            "--force",  # overwrite output_path if it already exists
            "-l",
            layer_name,
            "--drop-densest-as-needed",  # shed features rather than overflow a tile
        ]
        if max_zoom is not None:
            cmd += ["-z", str(max_zoom)]
        else:
            cmd += ["-zg"]  # guess an appropriate maximum zoom
        if min_zoom is not None:
            cmd += ["-Z", str(min_zoom)]
        if read_parallel:
            cmd += ["-P"]
        cmd.append(geojson_path)

        logger.info("Running tippecanoe: %s", " ".join(cmd))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError as e:
            raise RuntimeError(
                f"tippecanoe binary not found (looked for '{TIPPECANOE_BIN}'). "
                "Install tippecanoe or set the TIPPECANOE_BIN environment variable."
            ) from e

        if result.returncode != 0:
            logger.error(
                "tippecanoe failed (exit %s): %s", result.returncode, result.stderr
            )
            raise RuntimeError(
                f"tippecanoe failed with exit code {result.returncode}: "
                f"{result.stderr.strip()}"
            )
        return output_path
