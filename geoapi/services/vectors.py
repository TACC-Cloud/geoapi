import geopandas as gpd
from geoapi.log import logging
from typing import List, IO
import tempfile
import os


logger = logging.getLogger(__name__)

# additional files for FILE.shp
# (see https://desktop.arcgis.com/en/arcmap/10.3/manage-data/shapefiles/shapefile-file-extensions.htm)
SHAPEFILE_FILE_ADDITIONAL_FILES = {".shx": True,
                                   ".dbf": True,
                                   ".sbn": False, ".sbx": False,
                                   ".fbn": False, ".fbx": False,
                                   ".ain": False, ".aih": False,
                                   ".atx": False,
                                   ".ixs": False,
                                   ".mxs": False,
                                   ".prj": False,  # Note: feels like this should be True for our purposes
                                   ".xml": False,
                                   ".cpg": False}


class VectorService:
    """
    Utilities for handling vector files
    """

    @staticmethod
    def process_shapefile(shape_file: IO, additional_files: List[IO]):
        """ Process shapefile

        Loads shapefile and converts it to epsg 4326

        :param shape_file: IO
        :param additional_files: List[IO]   other files needed besides the main .shp file
        :return: generator that provides geometry plus properties for each item
        """
        all_files = additional_files.copy()
        all_files.append(shape_file)

        with tempfile.TemporaryDirectory() as tmpdirname:
            # save files together
            for f in all_files:
                tmp_path = os.path.join(tmpdirname, os.path.basename(f.filename))
                with open(tmp_path, 'wb') as tmp:
                    tmp.write(f.read())

            shapefile_path = os.path.join(tmpdirname, os.path.basename(shape_file.filename))
            shapefile = gpd.read_file(shapefile_path)
            shapefile.to_crs(epsg=4326)
            for index, row in shapefile.iterrows():
                properties = {}  # TODO
                yield row['geometry'], properties
