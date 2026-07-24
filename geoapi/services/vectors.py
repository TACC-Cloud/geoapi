import geopandas as gpd
from shapely import force_2d
from geoapi.log import logging
from typing import List, IO, Optional, Tuple
from pathlib import Path
import tempfile
import os

logger = logging.getLogger(__name__)

# Vector file extensions that are ingested via convert_to_geojson() -> tippecanoe -> PMTiles
#
# Deferred, not yet supported:
#   * gpkg (GeoPackage) — a multi-layer container (and can hold raster tiles).
#     Our "1 file = 1 Feature" model would silently ingest only the first layer.
#     Proper support means exploding its layers into N Features (+ handling any
#     embedded rasters as internal tile layers) — follow-on work.
#   * parquet/geoparquet — geopandas needs pyarrow (a heavyweight dep) and the
#     format is uncommon for our users. Re-adding is a one-dep change (add
#     pyarrow, restore the exts + a read_parquet branch in _read_direct).
SUPPORTED_VECTOR_EXTENSIONS = {
    "geojson",
    "json",
    "shp",
    "gpx",
}

# additional files for FILE.shp
# (see https://desktop.arcgis.com/en/arcmap/10.3/manage-data/shapefiles/shapefile-file-extensions.htm)
SHAPEFILE_FILE_ADDITIONAL_FILES = {
    ".shx": True,
    ".dbf": True,
    ".sbn": False,
    ".sbx": False,
    ".fbn": False,
    ".fbx": False,
    ".ain": False,
    ".aih": False,
    ".atx": False,
    ".ixs": False,
    ".mxs": False,
    ".prj": True,  # Note: listed as True for our purposes
    ".xml": False,
    ".cpg": False,
}


class VectorService:
    """
    Utilities for handling vector files
    """

    @staticmethod
    def convert_to_geojson(
        fileObj: IO, additional_files: Optional[List[IO]] = None
    ) -> Tuple[str, dict]:
        """Convert any supported vector file into a single EPSG:4326 GeoJSON file.

        Reads the file via geopandas, reprojects to EPSG:4326, strips Z
        coordinates, and computes the bounding box. The GeoJSON is written into a
        freshly-created temporary directory whose path is returned; the caller is
        responsible for removing that directory when finished with it.

        :param fileObj: main vector file (must have ``.filename`` and ``.read()``)
        :param additional_files: companion files (e.g. shapefile .dbf/.shx/.prj)
        :return: ``(geojson_path, bbox)`` where bbox is a dict with keys
            ``minx``, ``miny``, ``maxx``, ``maxy``
        """
        ext = Path(fileObj.filename).suffix.lstrip(".").lower()
        if ext == "shp":
            gdf = VectorService._read_shapefile(fileObj, additional_files or [])
        elif ext == "gpx":
            gdf = VectorService._read_gpx(fileObj)
        else:
            gdf = VectorService._read_direct(fileObj)

        if gdf.crs is None:
            # Inputs without a declared CRS (e.g. GeoJSON per RFC 7946) are WGS84
            gdf = gdf.set_crs(epsg=4326, allow_override=True)
        else:
            gdf = gdf.to_crs(epsg=4326)

        gdf = VectorService._force_2d(gdf)

        minx, miny, maxx, maxy = gdf.total_bounds
        bbox = {
            "minx": float(minx),
            "miny": float(miny),
            "maxx": float(maxx),
            "maxy": float(maxy),
        }

        out_dir = tempfile.mkdtemp(prefix="geoapi_vector_")
        geojson_path = os.path.join(out_dir, "converted.geojson")
        gdf.to_file(geojson_path, driver="GeoJSON")
        return geojson_path, bbox

    @staticmethod
    def _read_shapefile(shape_file: IO, additional_files: List[IO]) -> gpd.GeoDataFrame:
        """Read a shapefile (with its companion files) into a GeoDataFrame."""
        all_files = list(additional_files)
        all_files.append(shape_file)
        with tempfile.TemporaryDirectory() as tmpdirname:
            for f in all_files:
                tmp_path = os.path.join(tmpdirname, os.path.basename(f.filename))
                with open(tmp_path, "wb") as tmp:
                    tmp.write(f.read())
            shapefile_path = os.path.join(
                tmpdirname, os.path.basename(shape_file.filename)
            )
            return gpd.read_file(shapefile_path)

    @staticmethod
    def _read_gpx(fileObj: IO) -> gpd.GeoDataFrame:
        """Read the tracks layer of a GPX file into a GeoDataFrame."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmp_path = os.path.join(tmpdirname, os.path.basename(fileObj.filename))
            with open(tmp_path, "wb") as tmp:
                tmp.write(fileObj.read())
            return gpd.read_file(tmp_path, layer="tracks")

    @staticmethod
    def _read_direct(fileObj: IO) -> gpd.GeoDataFrame:
        """Read a self-contained vector file (geojson/json)."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmp_path = os.path.join(tmpdirname, os.path.basename(fileObj.filename))
            with open(tmp_path, "wb") as tmp:
                tmp.write(fileObj.read())
            return gpd.read_file(tmp_path)

    @staticmethod
    def _force_2d(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Drop Z (and M) coordinates from every geometry in the GeoDataFrame."""
        if gdf.empty:
            return gdf
        gdf = gdf.copy()
        gdf["geometry"] = gdf.geometry.apply(
            lambda geom: force_2d(geom) if geom is not None else geom
        )
        return gdf
