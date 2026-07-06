import os
import subprocess

from geoapi.log import logging

logger = logging.getLogger(__name__)

# tippecanoe binary; overridable for environments where it is not on PATH
TIPPECANOE_BIN = os.environ.get("TIPPECANOE_BIN", "tippecanoe")

# Floor for tippecanoe's guessed maximum zoom (-zg).
#
# `-zg` picks a max zoom from how far apart / how detailed the features are.
# For data whose features are simple and spread across a very large extent
# (e.g. a handful of points scattered globally, or continent-scale polygons)
# it can guess a max zoom of 0 — a single world tile. That is a problem for us:
#   * positions are then quantized to a ~10km grid (useless when zoomed in), and
#   * protomaps-leaflet cannot overzoom a zoom-0 archive (it treats
#     maxDataZoom 0 as falsy and defaults to 15, requesting tiles that don't
#     exist), so nothing renders.
# Flooring the guess to 12 (~sub-meter precision at the deepest tile) fixes both.
# The floor only *raises* low guesses; data with real local detail already
# guesses higher (e.g. dense reconnaissance points guess ~16) and is left
# untouched.
SMALLEST_MAXIMUM_ZOOM_GUESS = 12


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
    ) -> str:
        """
        Convert a GeoJSON file into a PMTiles archive using tippecanoe.

        :param geojson_path: path to the source GeoJSON file
        :param output_path: path where the .pmtiles archive will be written
        :param layer_name: name of the vector tile layer
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
            # guess an appropriate maximum zoom, but never below our floor
            # (see SMALLEST_MAXIMUM_ZOOM_GUESS for why sparse global data needs it)
            "-zg",
            f"--smallest-maximum-zoom-guess={SMALLEST_MAXIMUM_ZOOM_GUESS}",
            geojson_path,
        ]

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
