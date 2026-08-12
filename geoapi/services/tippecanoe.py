import os
import re
import subprocess
from typing import List, Optional, Tuple

from geoapi.log import logging

logger = logging.getLogger(__name__)

# tippecanoe binary; overridable for environments where it is not on PATH
TIPPECANOE_BIN = os.environ.get("TIPPECANOE_BIN", "tippecanoe")

# Zoom config for the combined published DesignSafe maps archive (WG-703).
#   min_zoom  z2  -- world overview (features are thinned below base_zoom; lets
#                    the layer show a sparse scatter when zoomed out)
#   base_zoom z8  -- every feature is kept at z8 and every zoom above (matches the
#                    ReconPortal's selectedEventZoomToLevel); below z8 they are thinned
#   max_zoom  z14 -- ~0.5m coordinate precision
PUBLISHED_DS_MAPS_MIN_ZOOM = 2
PUBLISHED_DS_MAPS_BASE_ZOOM = 8
PUBLISHED_DS_MAPS_MAX_ZOOM = 14

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
            # prefer adding zoom levels over dropping features (data fidelity);
            # runaway builds are bounded by the Celery task timeout
            "--extend-zooms-if-still-dropping",
            # keep every feature at every zoom (no thinning as you zoom out); by
            # default tippecanoe drops features at low zoom, so a scattered point
            # layer would show only ~1 point at the world view
            "--drop-rate=1",
            # shed features only if a tile would otherwise overflow
            "--drop-densest-as-needed",
            # guess maxzoom from feature spacing, but floor it so sparse/global
            # datasets don't get a near-zero maxzoom
            "-zg",
            # See SMALLEST_MAXIMUM_ZOOM_GUESS discussion above
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
        if result.stderr:
            logger.debug("tippecanoe output: %s", result.stderr)
        return output_path

    @staticmethod
    def geojson_layers_to_pmtiles(
        layers: List[Tuple[str, str]],
        output_path: str,
        min_zoom: int = PUBLISHED_DS_MAPS_MIN_ZOOM,
        base_zoom: int = PUBLISHED_DS_MAPS_BASE_ZOOM,
        max_zoom: int = PUBLISHED_DS_MAPS_MAX_ZOOM,
    ) -> Optional[int]:
        """
        Tile per-layer GeoJSON files into one PMTiles archive.

        Used for the combined published DesignSafe maps archive (WG-703). Unlike
        ``geojson_to_pmtiles`` (per-feature vector ingest, which guesses maxzoom),
        this pins a fixed zoom range and keeps features from ``base_zoom`` up
        (``-B``), where the ReconPortal actually looks (its selectedEventZoomToLevel),
        through overzoom. Below ``base_zoom`` they thin into a sparser
        overview. Tiles that would blow past the size cap shed their densest
        features at that zoom (``--drop-densest-as-needed``); those reappear at
        higher zoom where the tile fits (so no feature is lost from the archive).

        Each entry becomes its own vector-tile layer, so the consumer (i.e. ReconPortal)
        can style and toggle by feature type.

        :param layers: list of ``(layer_name, geojson_path)``
        :param output_path: path where the .pmtiles archive will be written
        :param min_zoom: minimum zoom (default z2)
        :param base_zoom: keep all features at/above this zoom; thin below (default z8)
        :param max_zoom: maximum zoom (default z14)
        :return: the feature count tippecanoe reports writing (for the caller's
            source-vs-archive count check), or ``None`` if it can't be parsed
        :raises RuntimeError: if the tippecanoe binary is missing or exits non-zero
        :raises ValueError: if ``layers`` is empty
        """
        if not layers:
            raise ValueError("geojson_layers_to_pmtiles requires at least one layer")

        cmd = [
            TIPPECANOE_BIN,
            "-o",
            output_path,
            "--force",  # overwrite output_path if it already exists
            "-Z",
            str(min_zoom),
            "-z",
            str(max_zoom),
            "-B",
            str(base_zoom),
            "--drop-densest-as-needed",
            "--no-feature-limit",
            "--no-tiny-polygon-reduction",
        ]
        for layer_name, geojson_path in layers:
            # `-L name:file` reads file into its own named vector-tile layer
            cmd += ["-L", f"{layer_name}:{geojson_path}"]

        logger.info("Running tippecanoe (public archive): %s", " ".join(cmd))
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

        return TippecanoeService._parse_written_feature_count(result.stderr)

    @staticmethod
    def _parse_written_feature_count(stderr: str) -> Optional[int]:
        """Pull the feature count out of tippecanoe's summary line.

        tippecanoe prints e.g. ``"3 features, 81 bytes of geometry ..."`` to
        stderr; this is the number of distinct input features it kept (it does
        not match the earlier ``"Read N million features"`` progress line).
        """
        match = re.search(r"(\d+) features,", stderr or "")
        return int(match.group(1)) if match else None
