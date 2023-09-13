import os
import pathlib
import uuid
import json
import tempfile
import configparser
from typing import List, IO, Dict

from geoapi.services.videos import VideoService
from shapely.geometry import Point, shape
import fiona
from geoalchemy2.shape import from_shape
import geojson

from geoapi.services.images import ImageService, ImageData
from geoapi.services.vectors import VectorService
from geoapi.models import Feature, FeatureAsset, Overlay, User, TileServer
from geoapi.exceptions import InvalidGeoJSON, ApiException
from geoapi.utils.assets import make_project_asset_dir, delete_assets, get_asset_relative_path
from geoapi.log import logging
from geoapi.utils import geometries
from geoapi.utils.agave import AgaveUtils

logger = logging.getLogger(__name__)


class FeaturesService:
    GEOJSON_FILE_EXTENSIONS = (
        'json', 'geojson'
    )

    IMAGE_FILE_EXTENSIONS = (
        'jpeg', 'jpg',
    )

    VIDEO_FILE_EXTENSIONS = (
        'mp4', 'mov', 'mpeg4', 'webm'
    )

    AUDIO_FILE_EXTENSIONS = (
        'mp3', 'aac'
    )

    GPX_FILE_EXTENSIONS = (
        'gpx',
    )

    SHAPEFILE_FILE_EXTENSIONS = (
        'shp',
    )

    RAPP_FILE_EXTENSIONS = (
        'rq',
    )

    ALLOWED_GEOSPATIAL_FEATURE_ASSET_EXTENSIONS = IMAGE_FILE_EXTENSIONS + VIDEO_FILE_EXTENSIONS

    INI_FILE_EXTENSIONS = (
        'ini',
    )

    ALLOWED_GEOSPATIAL_EXTENSIONS = IMAGE_FILE_EXTENSIONS + GPX_FILE_EXTENSIONS + GEOJSON_FILE_EXTENSIONS\
        + SHAPEFILE_FILE_EXTENSIONS
    # RAPP_FILE_EXTENSIONS to be added in https://jira.tacc.utexas.edu/browse/DES-2462

    ALLOWED_EXTENSIONS = IMAGE_FILE_EXTENSIONS + VIDEO_FILE_EXTENSIONS + AUDIO_FILE_EXTENSIONS + GPX_FILE_EXTENSIONS\
        + GEOJSON_FILE_EXTENSIONS + SHAPEFILE_FILE_EXTENSIONS + INI_FILE_EXTENSIONS
    # RAPP_FILE_EXTENSIONS to be added in https://jira.tacc.utexas.edu/browse/DES-2462

    @staticmethod
    def get(database_session, featureId: int) -> Feature:
        """
        Retreive a single Feature
        :param featureId: int
        :return: Feature
        """
        return database_session.query(Feature).get(featureId)

    @staticmethod
    def query(q: dict) -> List[Feature]:
        """
        Query/filter Features based on a bounding box or feature properties
        :param q: dict
        :return: GeoJSON
        """
        pass

    @staticmethod
    def delete(database_session, featureId: int) -> None:
        """
        Delete a Feature and any assets tied to it.
        :param featureId: int
        :return: None
        """
        feat = database_session.query(Feature).get(featureId)
        assets = database_session.query(FeatureAsset).filter(FeatureAsset.feature_id == featureId)
        for asset in assets:
            delete_assets(projectId=feat.project_id, uuid=asset.uuid)
        database_session.delete(feat)
        database_session.commit()

    @staticmethod
    def setProperties(database_session, featureId: int, props: Dict) -> Feature:
        """
        Set the properties of a feature.
        :param featureId: int
        :param props: dict
        :return: Feature
        """
        feat = database_session.query(Feature).get(featureId)
        # TODO: Throw assert if not found?
        # TODO: PROTECT assets and styles attributes
        feat.properties = props
        database_session.commit()
        return feat

    @staticmethod
    def setStyles(database_session, featureId: int, styles: Dict) -> Feature:
        """
        Set the styles of a feature.
        :param featureId: int
        :param styles: dict
        :return: Feature
        """
        feat = database_session.query(Feature).get(featureId)
        # TODO: PROTECT assets and styles attributes
        feat.styles = styles
        database_session.commit()
        return feat

    @staticmethod
    def addGeoJSON(database_session, projectId: int, feature: Dict, original_path=None) -> List[Feature]:
        """
        Add a GeoJSON feature to a project
        :param projectId: int
        :param feature: dict
        :return: Feature
        """
        try:
            data = geojson.loads(json.dumps(feature))
        except ValueError:
            raise InvalidGeoJSON
        features = []
        if data["type"] == "Feature":
            feat = Feature.fromGeoJSON(data)
            feat.project_id = projectId
            # strip out image_src, thumb_src if they are there from the old hazmapper geojson
            feat = FeaturesService._importHazmapperV1Images(feat)
            database_session.add(feat)
            features.append(feat)
        elif data["type"] == "FeatureCollection":
            fc = geojson.FeatureCollection(data)
            for feature in fc.features:
                feat = Feature.fromGeoJSON(feature)
                feat.project_id = projectId
                feat = FeaturesService._importHazmapperV1Images(feat)
                database_session.add(feat)
                features.append(feat)
        else:
            raise InvalidGeoJSON("Valid GeoJSON must be either a Feature or FeatureCollection.")
        database_session.commit()
        return features

    # TODO: we should be able to get rid of the old Hazmapper stuff at some point...
    @staticmethod
    def _importHazmapperV1Images(feat: Feature) -> Feature:
        if feat.properties.get("image_src"):
            imdata = ImageService.processBase64(feat.properties.get("image_src"))
            fa = FeaturesService.featureAssetFromImData(feat.project_id, imdata)
            feat.assets.append(fa)
            feat.properties.pop("image_src")
        if feat.properties.get("thumb_src"):
            feat.properties.pop("thumb_src")
        return feat

    @staticmethod
    def fromLatLng(database_session, projectId: int, lat: float, lng: float, metadata: Dict) -> Feature:
        point = Point(lng, lat)
        f = Feature()
        f.project_id = projectId
        f.the_geom = from_shape(point, srid=4326)
        f.properties = metadata or {}
        database_session.add(f)
        database_session.commit()
        return f

    @staticmethod
    def fromGPX(database_session, projectId: int, fileObj: IO, metadata: Dict, original_path=None) -> Feature:

        # TODO: Fiona should support reading from the file directly, this MemoryFile business
        #  should not be needed
        with fiona.io.MemoryFile(fileObj) as memfile:
            with memfile.open(layer="tracks") as collection:
                track = collection[0]
                shp = shape(track["geometry"])
                feat = Feature()
                feat.project_id = projectId
                feat.the_geom = from_shape(geometries.convert_3D_2D(shp), srid=4326)
                feat.properties = metadata or {}
                database_session.add(feat)
                database_session.commit()
                return feat

    @staticmethod
    def fromGeoJSON(database_session, projectId: int, fileObj: IO, metadata: Dict, original_path: str = None) -> List[Feature]:
        """

        :param projectId: int
        :param fileObj: file descriptor
        :param metadata: Dict of <key, val> pairs
        :param original_path: str path of original file location
        :return: Feature
        """
        data = json.loads(fileObj.read())
        fileObj.close()
        return FeaturesService.addGeoJSON(database_session, projectId, data)

    @staticmethod
    def fromShapefile(database_session, projectId: int, fileObj: IO, metadata: Dict, additional_files: List[IO],
                      original_path=None) -> Feature:
        """ Create features from shapefile

        :param projectId: int
        :param fileObj: file descriptor
        :param additional_files: file descriptor for all the other non-.shp files
        :param metadata: Dict of <key, val> pairs   [IGNORED}
        :param original_path: str path of original file location  [IGNORED}
        :return: Feature
        """
        features = []
        for geom, properties in VectorService.process_shapefile(fileObj, additional_files):
            feat = Feature()
            feat.project_id = projectId
            feat.the_geom = from_shape(geometries.convert_3D_2D(geom), srid=4326)
            feat.properties = properties
            database_session.add(feat)
            features.append(feat)

        database_session.commit()
        return features

    @staticmethod
    def fromRAPP(database_session, projectId: int, fileObj: IO, metadata: Dict, original_path: str = None) -> Feature:
        """

        :param projectId: int
        :param fileObj: file descriptor
        :param metadata: Dict of <key, val> pairs
        :param original_path: str path of original file location
        :return: Feature
        """
        data = json.loads(fileObj.read())

        lng = data.get('geolocation')[0].get('longitude')
        lat = data.get('geolocation')[0].get('latitude')
        point = Point(lng, lat)
        feat = Feature()
        feat.project_id = projectId
        feat.the_geom = from_shape(point, srid=4326)

        asset_uuid = uuid.uuid4()
        base_filepath = make_project_asset_dir(projectId)
        questionnaire_path = os.path.join(base_filepath, str(asset_uuid))
        pathlib.Path(questionnaire_path).mkdir(parents=True, exist_ok=True)
        asset_path = os.path.join(questionnaire_path, 'questionnaire.rq')

        with open(asset_path, 'w') as tmp:
            tmp.write(json.dumps(data))

        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="questionnaire",
            original_path=original_path,
            display_path=original_path,
            path=get_asset_relative_path(questionnaire_path),
            feature=feat,
        )
        feat.assets.append(fa)

        database_session.add(feat)
        database_session.commit()
        return feat

    @staticmethod
    def fromINI(database_session, projectId: int, fileObj: IO, metadata: Dict, original_path: str = None) -> TileServer:
        """

        :param projectId: int
        :param fileObj: file descriptor
        :param metadata: Dict of <key, val> pairs
        :param original_path: str path of original file location
        :return: Feature
        """
        config = configparser.ConfigParser(allow_no_value=True)
        config.read_string(fileObj.read().decode('utf-8'))

        tile_server_data = {}
        tile_server_data['tileOptions'] = {}
        tile_server_data['uiOptions'] = {}

        general_config = config['general']

        tile_server_data['name'] = general_config.get('id', '')
        tile_server_data['type'] = general_config.get('type', '').lower()

        if (config.has_section('license')):
            attribution = ''
            for key in config['license']:
                attribution += config['license'].get(key, '')
            tile_server_data['attribution'] = attribution
        else:
            tile_server_data['attribution'] = ''

        if (tile_server_data['type'] == 'tms'):
            tms_config = config['tms']
            tile_server_data['url'] = tms_config.get('url', fallback='')
            tile_server_data['tileOptions']['maxZoom'] = tms_config.getint('zmax', fallback=19)
            tile_server_data['tileOptions']['minZoom'] = tms_config.getint('zmin', fallback=0)
        elif (tile_server_data['type'] == 'wms'):
            wms_config = config['wms']
            tile_server_data['url'] = wms_config.get('url', fallback='')
            tile_server_data['tileOptions']['layers'] = wms_config.get('layers', fallback='')
            tile_server_data['tileOptions']['params'] = wms_config.get('params', fallback='')
            tile_server_data['tileOptions']['format'] = wms_config.get('format', fallback='')

        tile_server_data['uiOptions']['isActive'] = True
        tile_server_data['uiOptions']['opacity'] = 1

        fileObj.close()

        return FeaturesService.addTileServer(database_session, projectId, tile_server_data)

    @staticmethod
    def fromFileObj(database_session, projectId: int, fileObj: IO,
                    metadata: Dict, original_path: str = None, additional_files=None) -> List[Feature]:
        ext = pathlib.Path(fileObj.filename).suffix.lstrip(".").lower()
        if ext in FeaturesService.IMAGE_FILE_EXTENSIONS:
            return [FeaturesService.fromImage(database_session, projectId, fileObj, metadata, original_path)]
        elif ext in FeaturesService.GPX_FILE_EXTENSIONS:
            return [FeaturesService.fromGPX(database_session, projectId, fileObj, metadata, original_path)]
        elif ext in FeaturesService.GEOJSON_FILE_EXTENSIONS:
            return FeaturesService.fromGeoJSON(database_session, projectId, fileObj, {}, original_path)
        elif ext in FeaturesService.SHAPEFILE_FILE_EXTENSIONS:
            return FeaturesService.fromShapefile(database_session, projectId, fileObj, {}, additional_files, original_path)
        elif ext in FeaturesService.INI_FILE_EXTENSIONS:
            return FeaturesService.fromINI(database_session, projectId, fileObj, {}, original_path)
        elif False and ext in FeaturesService.RAPP_FILE_EXTENSIONS:  # Activate for https://jira.tacc.utexas.edu/browse/DES-2462
            return FeaturesService.fromRAPP(database_session, projectId, fileObj, {}, original_path)
        else:
            raise ApiException("Filetype not supported for direct upload. Create a feature and attach as an asset?")

    @staticmethod
    def fromImage(database_session, projectId: int, fileObj: IO, metadata: Dict, original_path: str = None) -> Feature:
        """
        Create a Point feature from a georeferenced image
        :param projectId: int
        :param fileObj: file
        :param metadata: dict
        :return: None
        """
        imdata = ImageService.processImage(fileObj)
        point = Point(imdata.coordinates)
        f = Feature()
        f.project_id = projectId
        f.the_geom = from_shape(point, srid=4326)
        f.properties = metadata

        asset_uuid = uuid.uuid4()
        base_filepath = make_project_asset_dir(projectId)
        asset_path = os.path.join(base_filepath, str(asset_uuid) + '.jpeg')

        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="image",
            original_path=original_path,
            display_path=original_path,
            path=get_asset_relative_path(asset_path),
            feature=f,
        )
        f.assets.append(fa)
        thumbnail_path = os.path.join(base_filepath, str(asset_uuid) + ".thumb.jpeg")
        resized_image_path = os.path.join(base_filepath, str(asset_uuid) + '.jpeg')
        try:
            imdata.thumb.save(thumbnail_path, "JPEG")
            imdata.resized.save(resized_image_path, "JPEG")
        except:  # noqa: E722
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            if os.path.exists(resized_image_path):
                os.remove(resized_image_path)
            raise
        finally:
            fileObj.close()
        database_session.add(f)
        database_session.commit()
        return f

    @staticmethod
    def createFeatureAsset(database_session, projectId: int, featureId: int, fileObj: IO, original_path: str = None) -> Feature:
        """
        Create a feature asset and save the static content to the ASSETS_BASE_DIR
        :param projectId: int
        :param featureId: int
        :param fileObj: file
        :return: Feature
        """
        fpath = pathlib.Path(fileObj.filename)
        ext = fpath.suffix.lstrip('.').lower()
        if ext in FeaturesService.IMAGE_FILE_EXTENSIONS:
            fa = FeaturesService.createImageFeatureAsset(projectId, fileObj, original_path=original_path)
        elif ext in FeaturesService.VIDEO_FILE_EXTENSIONS:
            fa = FeaturesService.createVideoFeatureAsset(projectId, fileObj, original_path=original_path)
        else:
            raise ApiException("Invalid format for feature assets")

        feat = FeaturesService.get(database_session, featureId)
        feat.assets.append(fa)
        database_session.commit()
        return feat

    @staticmethod
    def createFeatureAssetFromTapis(database_session, user: User, projectId: int, featureId: int, systemId: str, path: str) -> Feature:
        """
        Create a feature asset and save the static content to the ASSETS_BASE_DIR
        :param user: User
        :param projectId: int
        :param featureId: int
        :param fileObj: file
        :return: Feature
        """
        client = AgaveUtils(user.jwt)
        fileObj = client.getFile(systemId, path)
        fileObj.filename = pathlib.Path(path).name
        return FeaturesService.createFeatureAsset(database_session, projectId, featureId, fileObj, original_path=path)

    @staticmethod
    def featureAssetFromImData(projectId: int, imdata: ImageData) -> FeatureAsset:
        asset_uuid = uuid.uuid4()
        base_filepath = make_project_asset_dir(projectId)
        asset_path = os.path.join(base_filepath, str(asset_uuid) + '.jpeg')
        imdata.thumb.save(pathlib.Path(asset_path).with_suffix(".thumb.jpeg"), "JPEG")
        imdata.resized.save(asset_path, "JPEG")
        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="image",
            path=get_asset_relative_path(asset_path)
        )
        return fa

    @staticmethod
    def createImageFeatureAsset(projectId: int, fileObj: IO, original_path: str = None) -> FeatureAsset:
        asset_uuid = uuid.uuid4()
        imdata = ImageService.resizeImage(fileObj)
        base_filepath = make_project_asset_dir(projectId)
        asset_path = os.path.join(base_filepath, str(asset_uuid) + '.jpeg')
        imdata.thumb.save(pathlib.Path(asset_path).with_suffix(".thumb.jpeg"), "JPEG")
        imdata.resized.save(asset_path, "JPEG")
        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="image",
            original_path=original_path,
            display_path=original_path,
            path=get_asset_relative_path(asset_path)
        )
        return fa

    @staticmethod
    def createVideoFeatureAsset(projectId: int, fileObj: IO, original_path: str = None) -> FeatureAsset:
        """

        :param projectId:
        :param fileObj: Should be a file descriptor of a file in tmp
        :return: FeatureAsset
        """
        asset_uuid = uuid.uuid4()
        base_filepath = make_project_asset_dir(projectId)
        save_path = os.path.join(base_filepath, str(asset_uuid) + '.mp4')
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmp_path = os.path.join(tmpdirname, str(asset_uuid))
            with open(tmp_path, 'wb') as tmp:
                tmp.write(fileObj.read())
            encoded_path = VideoService.transcode(tmp_path)
            with open(encoded_path, 'rb') as enc:
                with open(save_path, 'wb') as f:
                    f.write(enc.read())
        # clean up the tmp file
        os.remove(encoded_path)
        fa = FeatureAsset(
            uuid=asset_uuid,
            original_path=original_path,
            display_path=original_path,
            path=get_asset_relative_path(save_path),
            asset_type="video"
        )
        return fa

    @staticmethod
    def clusterKMeans(database_session, projectId: int, numClusters: int = 20) -> Dict:
        """
        Cluster all the Point geometries in a project
        :param numClusters: int
        :param projectId: int
        :return: FeatureCollection
        """
        # TODO: Add filtering clause on the sub-select
        q = """
        select json_build_object(
               'type', 'FeatureCollection',
               'features', jsonb_agg(features.feature)
           )
        from (
                 select json_build_object(
                                'type', 'Feature',
                                'geometry', ST_AsGeoJSON(clusters.center)::jsonb,
                                'properties', json_build_object(
                                        'count', clusters.count
                                    )
                            ) as feature
                 from (
                          select ST_Centroid(ST_Collect(the_geom)) as center, count(clusters.cid) as count
                          from (
                                   SELECT ST_ClusterKMeans(the_geom, :numClusters) OVER () AS cid, the_geom
                                   from features
                                   where project_id = :projectId
                               ) as clusters
                          group by clusters.cid
                      ) as clusters
             ) as features
        """
        result = database_session.execute(q, {'projectId': projectId, 'numClusters': numClusters}).first()
        clusters = result[0]
        return clusters

    @staticmethod
    def addOverlay(database_session, projectId: int, fileObj: IO, bounds: List[float], label: str) -> Overlay:
        """

        :param projectId: int
        :param fileObj: IO
        :param bounds: List [minLon, minLat, maxLon, maxLat]
        :param label: str
        :return: None
        """

        imdata = ImageService.processOverlay(fileObj)
        ov = Overlay()
        ov.label = label
        ov.minLon = bounds[0]
        ov.minLat = bounds[1]
        ov.maxLon = bounds[2]
        ov.maxLat = bounds[3]
        ov.project_id = projectId
        ov.uuid = uuid.uuid4()
        asset_path = os.path.join(str(make_project_asset_dir(projectId)), str(ov.uuid) + '.jpeg')
        ov.path = get_asset_relative_path(asset_path)
        imdata.original.save(asset_path, 'JPEG')
        imdata.thumb.save(pathlib.Path(asset_path).with_suffix(".thumb.jpeg"), "JPEG")
        database_session.add(ov)
        database_session.commit()
        return ov

    @staticmethod
    def addOverlayFromTapis(database_session,
                            user: User, project_id: int, system_id: str,
                            path: str, bounds: List[float], label: str) -> Overlay:
        client = AgaveUtils(user.jwt)
        file_obj = client.getFile(system_id, path)
        ov = FeaturesService.addOverlay(database_session, project_id, file_obj, bounds, label)
        return ov

    @staticmethod
    def getOverlays(database_session, projectId: int) -> List[Overlay]:
        overlays = database_session.query(Overlay).filter_by(project_id=projectId).all()
        return overlays

    @staticmethod
    def deleteOverlay(database_session, projectId: int, overlayId: int) -> None:
        ov = database_session.query(Overlay).get(overlayId)
        delete_assets(projectId=projectId, uuid=ov.uuid)
        database_session.delete(ov)
        database_session.commit()

    @staticmethod
    def addTileServer(database_session, projectId: int, data: Dict):
        """
        :param projectId: int
        :param data: Dict
        :return: ts: TileServer
        """
        ts = TileServer()

        for key, value in data.items():
            setattr(ts, key, value)

        ts.project_id = projectId

        database_session.add(ts)
        database_session.commit()
        return ts

    @staticmethod
    def getTileServers(database_session, projectId: int) -> List[TileServer]:
        tile_servers = database_session.query(TileServer).filter_by(project_id=projectId).all()
        return tile_servers

    @staticmethod
    def deleteTileServer(database_session, tileServerId: int) -> None:
        ts = database_session.query(TileServer).get(tileServerId)
        database_session.delete(ts)
        database_session.commit()

    @staticmethod
    def updateTileServer(database_session, tileServerId: int, data: dict):
        ts = database_session.query(TileServer).get(tileServerId)
        for key, value in data.items():
            setattr(ts, key, value)
        database_session.commit()
        return ts

    @staticmethod
    def updateTileServers(database_session, dataList: List[dict]):
        ret_list = []
        for tsv in dataList:
            ts = database_session.query(TileServer).get(int(tsv['id']))
            for key, value in tsv.items():
                setattr(ts, key, value)
            ret_list.append(ts)
            database_session.commit()
        return ret_list
