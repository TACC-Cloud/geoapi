from flask import request, abort
from flask_restplus import Resource, Namespace, fields, inputs
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from geoapi.log import logging
from geoapi.schemas import FeatureSchema
from geoapi.services.features import FeaturesService
from geoapi.services.streetview import StreetviewService
from geoapi.services.point_cloud import PointCloudService
from geoapi.services.projects import ProjectsService
from geoapi.tasks import external_data, streetview
from geoapi.utils.decorators import (jwt_decoder, project_permissions_allow_public, project_permissions,
                                     project_feature_exists,  project_point_cloud_exists,
                                     project_point_cloud_not_processing, check_access_and_get_project, is_anonymous,
                                     not_anonymous, project_admin_or_creator_permissions)


logger = logging.getLogger(__name__)

api = Namespace('projects', decorators=[jwt_decoder])

ok_response = api.model('OkResponse', {
    "message": fields.String(default="accepted")
})

feature_schema = api.schema_model('Feature', FeatureSchema)

asset = api.model('Asset', {
    "id": fields.Integer(),
    "path": fields.String(),
    "uuid": fields.String(),
    "asset_type": fields.String(),
    "original_path": fields.String(),
    "original_name": fields.String(),
    "display_path": fields.String()
})

api_feature = api.model('Feature', {
    "id": fields.Integer(),
    "project_id": fields.Integer(),
    "type": fields.String(required=True, default="Feature"),
    "geometry": fields.Raw(required=True),
    "properties": fields.Raw(),
    "styles": fields.Raw(allow_null=True),
    "assets": fields.List(fields.Nested(asset), allow_null=True)
})

feature_collection_model = api.model('FeatureCollection', {
    "type": fields.String(required=True, default="FeatureCollection"),
    "features": fields.Nested(api_feature)
})

project = api.model('Project', {
    'id': fields.Integer(),
    'name': fields.String(required=True),
    'description': fields.String(required=False),
    'public': fields.Boolean(required=False),
    'uuid': fields.String(),
    'system_file': fields.String(),
    'system_id': fields.String(),
    'system_path': fields.String(),
})

#project_response = api.extend('Project', project, {
#    'deletable': fields.Boolean(),
#})

project_response = api.model('Project', {
    'id': fields.Integer(),
    'name': fields.String(required=True),
    'description': fields.String(required=False),
    'public': fields.Boolean(required=False),
    'uuid': fields.String(),
    'system_file': fields.String(),
    'system_id': fields.String(),
    'system_path': fields.String(),
    'deletable': fields.Boolean()
})

user = api.model('User', {
    'id': fields.Integer(),
    'username': fields.String(required=True)
})

task = api.model('Task', {
    'id': fields.Integer(),
    'status': fields.String(),
    'description': fields.String(required=False),
    'created': fields.DateTime(dt_format='rfc822'),
    'updated': fields.DateTime(dt_format='rfc822'),
})

point_cloud = api.model('PointCloud', {
    'id': fields.Integer(),
    'description': fields.String(required=False),
    'conversion_parameters': fields.String(required=False),
    'feature_id': fields.Integer(),
    'task': fields.Nested(task),
    'project_id': fields.Integer(),
    'files_info': fields.Raw(required=True)
})

overlay = api.model('Overlay', {
    'id': fields.Integer(),
    'uuid': fields.String(),
    'minLon': fields.Float(),
    'minLat': fields.Float(),
    'maxLon': fields.Float(),
    'maxLat': fields.Float(),
    'path': fields.String(),
    'project_id': fields.Integer(),
    'label': fields.String()
})

tile_server = api.model('TileServer', {
    'id': fields.Integer(required=False),
    'name': fields.String(),
    'type': fields.String(),
    'url': fields.String(),
    'attribution': fields.String(),
    'tileOptions': fields.Raw(allow_null=True),
    'uiOptions': fields.Raw(allow_null=True)
})

file_upload_parser = api.parser()
file_upload_parser.add_argument('file', location='files', type=FileStorage, required=True)

tapis_file_upload_body = api.model('TapisFileUpload', {
    "system_id": fields.String(),
    "path": fields.String()
})

tapis_file = api.model('TapisFile', {
    'system': fields.String(required=True),
    'path': fields.String(required=True)
})

tapis_save_file = api.model('TapisSaveFile', {
    'system_id': fields.String(required=True),
    'path': fields.String(required=True),
    'file_name': fields.String(required=True),
    'observable': fields.Boolean(required=False),
    'watch_content': fields.Boolean(required=False)
})

tapis_files_import = api.model('TapisFileImport', {
    'files': fields.List(fields.Nested(tapis_file), required=True)
})

overlay_parser = api.parser()
overlay_parser.add_argument('file', location='files', type=FileStorage, required=True)
overlay_parser.add_argument('label', location=('form', 'json'), type=str, required=True)
overlay_parser.add_argument('minLon', location=('form', 'json'), type=float, required=True)
overlay_parser.add_argument('minLat', location=('form', 'json'), type=float, required=True)
overlay_parser.add_argument('maxLon', location=('form', 'json'), type=float, required=True)
overlay_parser.add_argument('maxLat', location=('form', 'json'), type=float, required=True)

overlay_parser_tapis = overlay_parser.copy()
overlay_parser_tapis.remove_argument('file')
overlay_parser_tapis.add_argument('system_id', location='json', type=str, required=True)
overlay_parser_tapis.add_argument('path', location='json', type=str, required=True)


@api.route('/')
class ProjectsListing(Resource):

    parser = api.parser()
    parser.add_argument('uuid', location='args', action='split',
                        help="uuid of specific projects to return instead of complete list")

    @api.doc(id="getProjects",
             description='Get a listing of projects',
             parser=parser)
    @api.marshal_with(project_response, as_list=True)
    def get(self):
        u = request.current_user
        query = self.parser.parse_args()
        uuid_subset = query.get("uuid")

        if uuid_subset:
            logger.info("Get a subset of projects for user:{} projects:{}".format(u.username, uuid_subset))
            # Check each project and abort if user (authenticated or anonymous) can't access the project
            subset = [check_access_and_get_project(request.current_user, uuid=uuid, allow_public_use=True) for uuid in uuid_subset]
            return subset
        else:
            if is_anonymous(u):
                abort(403, "Access denied")
            logger.info("Get all projects for user:{}".format(u.username))
            return ProjectsService.list(u)

    @api.doc(id="createProject",
             description='Create a new project')
    @api.expect(project)
    @api.marshal_with(project_response)
    @not_anonymous
    def post(self):
        u = request.current_user
        logger.info("Create project for user:{} : {}".format(u.username,
                                                             api.payload))
        return ProjectsService.create(api.payload, u)


@api.route('/<int:projectId>/')
class ProjectResource(Resource):

    @api.doc(id="getProjectById",
             description="Get the metadata about a project")
    @api.marshal_with(project_response)
    @project_permissions_allow_public
    def get(self, projectId: int):
        u = request.current_user
        logger.info("Get metadata project:{} for user:{}".format(projectId, u.username))
        return ProjectsService.get(project_id=projectId, user=u)

    @api.doc(id="deleteProject",
             description="Delete a project, all associated features and metadata. THIS CANNOT BE UNDONE")
    @project_admin_or_creator_permissions
    def delete(self, projectId: int):
        u = request.current_user
        logger.info("Delete project:{} for user:{}".format(projectId,
                                                           u.username))
        return ProjectsService.delete(u, projectId)

    @api.doc(id="updateProject",
             description="Update metadata about a project")
    @api.marshal_with(project_response)
    @project_permissions
    def put(self, projectId: int):
        u = request.current_user
        logger.info("Update project:{} for user:{}".format(projectId,
                                                           u.username))
        return ProjectsService.update(user=u,
                                      projectId=projectId,
                                      data=api.payload)


@api.route('/<int:projectId>/users/')
class ProjectUsersResource(Resource):
    @api.marshal_with(user, as_list=True)
    @project_permissions
    def get(self, projectId: int):
        return ProjectsService.getUsers(projectId)

    @api.doc(id="addUser",
             description="Add a user to the project. This allows full access to the project, "
                         "including deleting the entire thing so chose carefully")
    @api.expect(user)
    @project_permissions
    def post(self, projectId: int):
        payload = request.json
        username = payload["username"]
        logger.info("Add user:{} to project:{} for user:{}".format(
            username,
            projectId,
            request.current_user.username))
        ProjectsService.addUserToProject(projectId, username)
        return "ok"


@api.route('/<int:projectId>/users/<username>/')
class ProjectUserResource(Resource):
    @api.doc(id="removeUser",
             description="Remove a user from a project")
    @project_permissions
    def delete(self, projectId: int, username: str):
        logger.info("Delete user:{} from project:{} for user:{}".format(
            username,
            projectId,
            request.current_user.username))
        return ProjectsService.removeUserFromProject(projectId,
                                                     username)


@api.route('/<int:projectId>/features/')
class ProjectFeaturesResource(Resource):
    parser = api.parser()
    parser.add_argument("assetType", location="args")
    parser.add_argument('bbox',
                        location='args',
                        action='split',
                        type=float,
                        help="bounding box: min longitude, min latitude, max longitude, max latitude "
                             "(i.e bbox=minLon,minLat, maxLon,maxLat")
    parser.add_argument('startDate', location='args', type=inputs.datetime_from_iso8601,
                        help="Starting date for filtering of features by created date."
                             " endDate is also required.")
    parser.add_argument('endDate', location='args', type=inputs.datetime_from_iso8601,
                        help="Ending date for filtering features by created date. "
                             " startDate is also required.")

    @api.doc(id="getAllFeatures",
             parser=parser,
             description="GET all the features of a project as GeoJSON")
    @api.marshal_with(feature_collection_model, as_list=True)
    @project_permissions_allow_public
    def get(self, projectId: int):
        logger.info("Get features of project:{} for user:{}".format(
            projectId, request.current_user.username))
        query = self.parser.parse_args()
        return ProjectsService.getFeatures(projectId, query)

    @api.doc(id="addGeoJSONFeature",
             description="Add a GeoJSON feature to a project")
    @api.marshal_with(api_feature)
    @api.expect(feature_schema)
    @project_permissions
    def post(self, projectId: int):
        logger.info("Add GeoJSON feature to project:{} for user:{}".format(
            projectId, request.current_user.username))
        return FeaturesService.addGeoJSON(projectId, request.json)


@api.route('/<int:projectId>/features/<int:featureId>/')
class ProjectFeatureResource(Resource):
    @api.doc(id="getFeature",
             description="GET a feature of a project as GeoJSON")
    @api.marshal_with(api_feature)
    @project_permissions_allow_public
    def get(self, projectId: int, featureId: int):
        return FeaturesService.get(featureId)

    @api.doc(id="deleteFeature",
             description="GET a feature of a project as GeoJSON")
    @api.marshal_with(ok_response)
    @project_permissions
    def delete(self, projectId: int, featureId: int):
        logger.info("Delete feature:{} from project:{} for user:{}".format(
            featureId, projectId, request.current_user.username))
        return FeaturesService.delete(featureId)


@api.route('/<int:projectId>/features/<int:featureId>/properties/')
class ProjectFeaturePropertiesResource(Resource):

    @api.doc(id="updateFeatureProperties",
             description="Update the properties of a feature. This will replace any"
                         "existing properties previously associated with the feature")
    @api.marshal_with(api_feature)
    @project_permissions
    @project_feature_exists
    def post(self, projectId: int, featureId: int):
        return FeaturesService.setProperties(featureId, request.json)


@api.route('/<int:projectId>/features/<int:featureId>/styles/')
class ProjectFeatureStylesResource(Resource):

    @api.doc(id="updateFeatureStyles",
             description="Update the styles of a feature. This will replace any styles"
                         "previously associated with the feature.")
    @api.marshal_with(api_feature)
    @project_permissions
    @project_feature_exists
    def post(self, projectId: int, featureId: int):
        return FeaturesService.setStyles(featureId, request.json)


@api.route('/<int:projectId>/features/<int:featureId>/assets/')
class ProjectFeaturesCollectionResource(Resource):

    @api.doc(id="addFeatureAsset",
             description='Add a static asset to a collection. Must be an image or video at the moment')
    @api.expect(tapis_file_upload_body)
    @api.marshal_with(api_feature)
    @project_permissions
    @project_feature_exists
    def post(self, projectId: int, featureId: int):
        systemId = request.json["system_id"]
        path = request.json["path"]
        u = request.current_user
        logger.info("Add feature asset to project:{} for user:{}: {}/{}".format(
            projectId, u.username, systemId, path))
        return FeaturesService.createFeatureAssetFromTapis(u, projectId, featureId, systemId, path)


@api.route('/<int:projectId>/features/files/')
class ProjectFeaturesFilesResource(Resource):

    @api.doc(id="uploadFile",
             description='Add a new feature(s) to a project from a file that has embedded geospatial information. Current '
                         'allowed file types are GeoJSON, georeferenced image (jpeg) or gpx track. '
                         'Any additional key/value pairs '
                         'in the form will also be placed in the feature(s) metadata')
    @api.expect(file_upload_parser)
    @api.marshal_with(api_feature, as_list=True)
    @project_permissions
    def post(self, projectId: int):
        file = request.files['file']
        logger.info("Add feature to project:{} for user:{} : {}".format(
            projectId, request.current_user.username, file.filename))
        formData = request.form
        metadata = formData.to_dict()
        features = FeaturesService.fromFileObj(projectId, file, metadata)
        return features


@api.route('/<int:projectId>/features/files/import/')
class ProjectFeaturesFileImportResource(Resource):
    @api.doc(id="importFileFromTapis",
             description='Import a file into a project from Tapis. Current '
                         'allowed file types are georeferenced image (jpeg), gpx tracks, GeoJSON and shape files. This'
                         'is an asynchronous operation, files will be imported in the background'
             )
    @api.expect(tapis_files_import)
    @api.marshal_with(ok_response)
    @project_permissions
    def post(self, projectId: int):
        u = request.current_user
        logger.info("Import feature to project:{} for user:{} : {}".format(
            projectId, request.current_user.username, request.json["files"]))
        for file in request.json["files"]:
            external_data.import_file_from_agave.delay(u.id, file["system"], file["path"], projectId)
        return {"message": "accepted"}


@api.route('/<int:projectId>/features/cluster/<int:numClusters>/')
class ProjectFeaturesClustersResource(Resource):

    @api.doc(id="clusterFeatures",
             description='K-Means cluster the features in a project. This returns a FeatureCollection '
                         'of the centroids with the additional property of "count" representing the number of '
                         'Features that were aggregated into each cluster')
    @api.marshal_with(feature_collection_model)
    @project_permissions
    def get(self, projectId: int, numClusters: int):
        clusters = FeaturesService.clusterKMeans(projectId, numClusters)
        return clusters


@api.route('/<int:projectId>/overlays/')
class ProjectOverlaysResource(Resource):
    @api.doc(id="addOverlay",
             description='Add a new overlay to a project.')
    @api.expect(overlay_parser, validate=True)
    @api.marshal_with(overlay)
    @project_permissions
    def post(self, projectId: int):
        file = request.files['file']

        logger.info("Add overlay to project:{} for user:{} : {}".format(
            projectId, request.current_user.username, file.filename))

        formData = request.form
        bounds = [
            formData['minLon'],
            formData['minLat'],
            formData['maxLon'],
            formData['maxLat']
        ]
        label = formData['label']
        ov = FeaturesService.addOverlay(projectId, file, bounds, label)
        return ov

    @api.doc(id="getOverlays",
             description='Get a list of all the overlays associated with the current map project.')
    @api.marshal_with(overlay, as_list=True)
    @project_permissions_allow_public
    def get(self, projectId: int):
        ovs = FeaturesService.getOverlays(projectId)
        return ovs


@api.route('/<int:projectId>/overlays/import/')
class ProjectOverlaysImportResource(Resource):
    @api.doc(id="importOverlayFromTapis",
             description='Import an overlay from Tapis')
    @api.expect(overlay_parser_tapis, validate=True)
    @api.marshal_with(overlay)
    @project_permissions
    def post(self, projectId: int):
        u = request.current_user
        logger.info("Import overlay to project:{} for user:{} : {}".format(
            projectId, u.username, request.json))
        systemId = request.json['system_id']
        path = request.json['path']
        label = request.json['label']
        bounds = [
            request.json['minLon'],
            request.json['minLat'],
            request.json['maxLon'],
            request.json['maxLat']
        ]
        ov = FeaturesService.addOverlayFromTapis(u, projectId, systemId, path, bounds, label)
        return ov


@api.route('/<int:projectId>/overlays/<int:overlayId>/')
class ProjectOverlayResource(Resource):

    @api.doc(id="removeOverlay",
             description='Remove an overlay from a project')
    @project_permissions
    def delete(self, projectId: int, overlayId: int) -> str:
        logger.info("Delete overlay:{} in project:{} for user:{}".format(
            overlayId, projectId, request.current_user.username))
        FeaturesService.deleteOverlay(projectId, overlayId)
        return "Overlay {id} deleted".format(id=overlayId)


@api.route('/<int:projectId>/streetview/')
class ProjectStreetviewResource(Resource):
    @api.doc(id="addStreetviewSequenceToFeature",
             description="Add a streetview sequence to a project feature")
    @api.marshal_with(task)
    @project_permissions
    def post(self, projectId: int):
        logger.info("Add streetview sequence to project features:{} for user:{}".format(
            projectId, request.current_user.username))
        sequenceId = api.payload['sequenceId']
        token = api.payload['token']['token']
        return streetview.process_streetview_sequences(projectId, sequenceId, token)


@api.route('/<int:projectId>/streetview/<int:featureId>/')
class ProjectStreetviewFeatureResource(Resource):
    @api.doc(id="getStreetviewSequenceFromFeature",
             description="Get a streetview sequence from a project feature")
    @project_permissions
    def get(self, projectId: int, featureId: int):
        logger.info("Get streetview sequence from project features:{} for user:{}".format(
            projectId, request.current_user.username))
        return StreetviewService.sequenceFromFeature(featureId)


@api.route('/<int:projectId>/point-cloud/')
class ProjectPointCloudsResource(Resource):

    @api.doc(id="getAllPointClouds",
             description="Get a listing of all the points clouds of a project")
    @api.marshal_with(point_cloud, as_list=True)
    @project_permissions_allow_public
    def get(self, projectId: int):
        return PointCloudService.list(projectId)

    @api.doc(id="addPointCloud",
             description="Add a point cloud to a project")
    @api.marshal_with(point_cloud)
    @api.expect(point_cloud)
    @project_permissions
    def post(self, projectId: int):
        logger.info("Add point cloud to project:{} for user:{}".format(
            projectId, request.current_user.username))
        return PointCloudService.create(projectId=projectId,
                                        user=request.current_user,
                                        data=api.payload)


@api.route('/<int:projectId>/point-cloud/<int:pointCloudId>/')
class ProjectPointCloudResource(Resource):

    @api.doc(id="getPointCloud",
             description="Get point cloud of a project")
    @api.marshal_with(point_cloud)
    @project_permissions_allow_public
    def get(self, projectId: int, pointCloudId: int):
        return PointCloudService.get(pointCloudId)

    @api.doc(id="uploadPointCloud",
             description='Add a file to a point cloud. Current allowed file types are las and laz.')
    @api.expect(file_upload_parser)
    @api.marshal_with(task)
    @project_permissions
    @project_point_cloud_exists
    @project_point_cloud_not_processing
    def post(self, projectId: int, pointCloudId: int):
        """
        :raises InvalidCoordinateReferenceSystem: in case  file missing coordinate reference system
        """
        f = request.files['file']
        file_name = secure_filename(f.filename)
        logger.info("Add a file to a point cloud:{} in project:{} for user:{}: {}".format(
            pointCloudId, projectId, request.current_user.username, file_name))
        pc_task = PointCloudService.fromFileObj(pointCloudId, f, file_name)
        return pc_task

    @api.doc(id="updatePointCLoud",
             description="Update point cloud")
    @api.marshal_with(point_cloud)
    @api.expect(point_cloud)
    @project_permissions
    @project_point_cloud_exists
    @project_point_cloud_not_processing
    def put(self, projectId: int, pointCloudId: int):
        # TODO consider adding status to point cloud as we aren't returning task
        return PointCloudService.update(pointCloudId=pointCloudId,
                                        data=api.payload)

    @api.doc(id="deletePointCloud",
             description="Delete point cloud, all associated point cloud files will be deleted "
                         "(however associated feature and feature asset will not be deleted). "
                         "THIS CANNOT BE UNDONE")
    @project_permissions
    @project_point_cloud_exists
    @project_point_cloud_not_processing
    def delete(self, projectId: int, pointCloudId: int):
        logger.info("Delete point cloud:{} in project:{} for user:{}".format(
            pointCloudId, projectId, request.current_user.username))
        return PointCloudService.delete(pointCloudId)


@api.route('/<int:projectId>/point-cloud/<int:pointCloudId>/import/')
class ProjectPointCloudsFileImportResource(Resource):
    @api.doc(id="importPointCloudFileFromTapis",
             description='Import a point cloud file into a project from Tapis. Current '
                         'allowed file types are las and laz. This is an asynchronous operation, '
                         'files will be imported in the background'
             )
    @api.expect(tapis_files_import)
    @api.marshal_with(ok_response)
    @project_permissions
    @project_point_cloud_exists
    @project_point_cloud_not_processing
    def post(self, projectId: int, pointCloudId: int):
        u = request.current_user
        files = request.json["files"]
        logger.info("Import file(s) to a point cloud:{} in project:{} for user:{}: {}".format(
            pointCloudId, projectId, request.current_user.username, files))

        for file in files:
            PointCloudService.check_file_extension(file["path"])

        external_data.import_point_clouds_from_agave.delay(u.id, files, pointCloudId)
        return {"message": "accepted"}


@api.route('/<int:projectId>/tasks/')
class ProjectTasksResource(Resource):

    @api.doc(id="getTasks",
             description="Get a listing of all the tasks of a project")
    @api.marshal_with(task, as_list=True)
    @project_permissions
    def get(self, projectId: int):
        from geoapi.db import db_session
        from geoapi.models import Task
        return db_session.query(Task).all()


@api.route('/<int:projectId>/tile-servers/')
class ProjectTileServersResource(Resource):
    @api.doc(id="addTileServer",
             description='Add a new tile server to a project.')
    @api.expect(tile_server)
    @api.marshal_with(tile_server)
    @project_permissions
    def post(self, projectId: int):
        logger.info("Add tile server to project:{} for user:{}".format(
            projectId, request.current_user.username))

        ts = FeaturesService.addTileServer(projectId, api.payload)
        return ts

    @api.doc(id="getTileServers",
             description='Get a list of all the tile servers associated with the current map project.')
    @api.marshal_with(tile_server, as_list=True)
    @project_permissions_allow_public
    def get(self, projectId: int):
        tsv = FeaturesService.getTileServers(projectId)
        return tsv

    @api.doc(id="updateTileServers",
             description="Update metadata about a tile servers")
    @api.marshal_with(tile_server, as_list=True)
    @project_permissions
    def put(self, projectId: int):
        u = request.current_user
        logger.info("Update project:{} for user:{}".format(projectId,
                                                           u.username))

        ts = FeaturesService.updateTileServers(dataList=api.payload)
        return ts


@api.route('/<int:projectId>/tile-servers/<int:tileServerId>/')
class ProjectTileServerResource(Resource):

    @api.doc(id="removeTileServer",
             description='Remove a tile server from a project')
    @project_permissions
    def delete(self, projectId: int, tileServerId: int) -> str:
        logger.info("Delete tile server:{} in project:{} for user:{}".format(
            tileServerId, projectId, request.current_user.username))
        FeaturesService.deleteTileServer(tileServerId)
        return "Tile Server {id} deleted".format(id=tileServerId)

    @api.doc(id="updateTileServer",
             description="Update metadata about a tile server")
    @api.marshal_with(tile_server)
    @project_permissions
    def put(self, projectId: int, tileServerId: int):
        u = request.current_user
        logger.info("Update project:{} for user:{}".format(projectId,
                                                           u.username))

        return FeaturesService.updateTileServer(tileServerId=tileServerId,
                                                data=api.payload)
