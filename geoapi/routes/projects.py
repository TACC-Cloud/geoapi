from flask import request, abort
from flask_restplus import Resource, Namespace, fields
from werkzeug.datastructures import FileStorage

from geoapi.log import logging
from geoapi.schemas import FeatureSchema
from geoapi.services.features import FeaturesService
from geoapi.services.projects import ProjectsService
from geoapi.services.point_cloud import PointCloudService
from geoapi.utils.decorators import jwt_decoder, project_permissions, project_feature_exists, project_point_cloud_exists

logger = logging.getLogger(__name__)

api = Namespace('projects', decorators=[jwt_decoder])

default_response = api.model('DefaultAgaveResponse', {
    "message": fields.String(),
    "version": fields.String(),
    "status": fields.String(default="success")
})

feature_schema = api.schema_model('Feature', FeatureSchema)

asset = api.model('Asset', {
    "id": fields.Integer(),
    "path": fields.String(),
    "uuid": fields.String(),
    "asset_type": fields.String()
})

api_feature = api.model('Feature', {
    "id": fields.Integer(),
    "type": fields.String(required=True, default="Feature"),
    "geometry": fields.Raw(required=True),
    "properties": fields.Raw(),
    "styles": fields.Raw(allow_null=True),
    "assets": fields.Nested(asset, allow_null=True)
})

feature_collection_model = api.model('FeatureCollection', {
    "type": fields.String(required=True, default="FeatureCollection"),
    "features": fields.Nested(api_feature)
})

project = api.model('Project', {
    'id': fields.Integer(),
    'name': fields.String(required=True),
    'description': fields.String(required=False),
    'uuid': fields.String(),
})

user = api.model('User', {
    'id': fields.Integer(),
    'username': fields.String(required=True)
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

point_cloud = api.model('PointCloud', {
    'id': fields.Integer(),
    'description': fields.String(required=False),
    'conversion_parameters': fields.String(required=False),
    'feature_id': fields.Integer(),
    'task_id' : fields.Integer()
})

task = api.model('Task', {
    'id': fields.Integer(),
    'status': fields.String(),
    'description': fields.String(required=False),
    'created': fields.DateTime(dt_format='rfc822'),
    'updated': fields.DateTime(dt_format='rfc822')
})

overlay_parser = api.parser()
overlay_parser.add_argument('file', location='files', type=FileStorage, required=True)
overlay_parser.add_argument('label', location='form', type=str, required=True)
overlay_parser.add_argument('minLon', location='form', type=float, required=True)
overlay_parser.add_argument('minLat', location='form', type=float, required=True)
overlay_parser.add_argument('maxLon', location='form', type=float, required=True)
overlay_parser.add_argument('maxLat', location='form', type=float, required=True)

rapid_project_body = api.model("RapidProject", {
    "system_id": fields.String(),
    "path": fields.String(default="RApp")
})

file_upload_parser = api.parser()
file_upload_parser.add_argument('file', location='files', type=FileStorage, required=True)


@api.route('/')
class ProjectsListing(Resource):

    @api.doc(id="getProjects",
             description='Get a listing of projects')
    @api.marshal_with(project)
    def get(self):
        u = request.current_user
        return ProjectsService.list(u)

    @api.doc(id="createProject",
             description='Create a new project')
    @api.expect(project)
    @api.marshal_with(project)
    def post(self):
        u = request.current_user
        return ProjectsService.create(api.payload, u)


@api.route('/rapid/')
class RapidProject(Resource):
    @api.doc(id="createRapidProject",
             description='Create a new project from a Rapid recon project storage system')
    @api.expect(rapid_project_body)
    @api.marshal_with(project)
    def post(self):
        u = request.current_user
        try:
            return ProjectsService.createRapidProject(api.payload, u)
        except Exception as e:
            logger.exception(e)
            return abort(409, "A project for this storage system/path already exists!")


@api.route('/<int:projectId>/')
class ProjectResource(Resource):

    @api.doc(id="getProjectById",
             description="Get the metadata about a project")
    @api.marshal_with(project)
    @project_permissions
    def get(self, projectId: int):
        return ProjectsService.get(projectId)

    @api.doc(id="deleteProject",
             description="Delete a project, all associated features and metadata. THIS CANNOT BE UNDONE")
    @project_permissions
    def delete(self, projectId: int):
        return ProjectsService.delete(projectId)

    @api.doc(id="updateProject",
             description="Update metadata about a project")
    @project_permissions
    def put(self, projectId: int):
        return True


@api.route('/<int:projectId>/users/')
class ProjectUsersResource(Resource):

    @api.marshal_with(user)
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
        ProjectsService.addUserToProject(projectId, username)
        return "ok"


@api.route('/<int:projectId>/users/<username>/')
class ProjectUserResource(Resource):

    @api.doc(id="removeUser",
             description="Remove a user from a project")
    @project_permissions
    def delete(self, projectId: int):
        return ProjectsService.removeUserFromProject(projectId, request.current_user.username)


@api.route('/<int:projectId>/features/')
class ProjectFeaturesResource(Resource):

    @api.doc(id="getAllFeatures",
             description="GET all the features of a project as GeoJSON")
    @api.marshal_with(feature_collection_model)
    @project_permissions
    def get(self, projectId: int):
        query = request.args
        return ProjectsService.getFeatures(projectId, query)

    @api.doc(id="addGeoJSONFeature",
             description="Add a GeoJSON feature to a project")
    @api.marshal_with(api_feature)
    @api.expect(feature_schema)
    @project_permissions
    def post(self, projectId: int):
        return FeaturesService.addGeoJSON(projectId, request.json)


@api.route('/<int:projectId>/features/<int:featureId>/')
class ProjectFeatureResource(Resource):
    @api.doc(id="getFeature",
             description="GET all the features of a project as GeoJSON")
    @api.marshal_with(api_feature)
    @project_permissions
    def get(self, projectId: int, featureId: int):
        return FeaturesService.get(featureId)


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
class ProjectFeaturePropertiesResource(Resource):

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
    @api.expect(file_upload_parser)
    @api.marshal_with(api_feature)
    @project_permissions
    @project_feature_exists
    def post(self, projectId: int, featureId: int):
        args = file_upload_parser.parse_args()
        return FeaturesService.createFeatureAsset(projectId, featureId, args['file'])


@api.route('/<int:projectId>/features/files/')
class ProjectFeaturesFilesResource(Resource):

    @api.doc(id="uploadFile",
             description='Add a new feature to a project from a file that has embedded geospatial information. Current '
                         'allowed file types are georeferenced image (jpeg) or gpx track. '
                         'Any additional key/value pairs '
                         'in the form will also be placed in the feature metadata')
    @api.expect(file_upload_parser)
    @api.marshal_with(api_feature)
    @project_permissions
    def post(self, projectId: int):
        file = request.files['file']
        formData = request.form
        metadata = formData.to_dict()
        feature = FeaturesService.fromFileObj(projectId, file, metadata)
        return feature


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
    @api.expect(overlay_parser)
    @api.marshal_with(overlay)
    @project_permissions
    def post(self, projectId: int):
        file = request.files['file']
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
    @api.marshal_with(overlay)
    @project_permissions
    def get(self, projectId: int):
        ovs = FeaturesService.getOverlays(projectId)
        return ovs


@api.route('/<int:projectId>/overlays/<int:overlayId>/')
class ProjectOverlayResource(Resource):

    @api.doc(id="removeOverlay",
             description='Remove an overlay from a project')
    @project_permissions
    def delete(self, projectId: int, overlayId: int) -> str:
        FeaturesService.deleteOverlay(projectId, overlayId)
        return "Overlay {id} deleted".format(id=overlayId)


@api.route('/<int:projectId>/point-cloud/')
class ProjectPointCloudsResource(Resource):

    @api.doc(id="getAllPointClouds",
             description="Get a listing of all the points clouds of a project")
    @api.marshal_with(point_cloud)
    @project_permissions
    def get(self, projectId: int):
        return PointCloudService.list(projectId)

    @api.doc(id="addPointCloud",
             description="Add a point cloud to a project")
    @api.marshal_with(point_cloud)
    @api.expect(point_cloud)
    @project_permissions
    def post(self, projectId: int):
        return PointCloudService.create(projectId=projectId,
                                        user=request.current_user,
                                        data=request.json)


@api.route('/<int:projectId>/point-cloud/<int:pointCloudId>/')
class ProjectPointCloudResource(Resource):

    @api.doc(id="getPointCloud",
             description="Get point cloud of a project")
    @api.marshal_with(point_cloud)
    @project_permissions
    def get(self, projectId: int, pointCloudId: int):
        return PointCloudService.get(pointCloudId)

    @api.doc(id="uploadPointCloud",
             description='Add a file to a point cloud. Current allowed file types are las and laz. Any additional '
                         'key/value pairs in the form will also be placed in the feature metadata')
    @api.expect(file_upload_parser)
    @api.marshal_with(task)
    @project_permissions
    @project_point_cloud_exists
    def post(self, projectId: int, pointCloudId: int):
        file = request.files['file']
        formData = request.form
        metadata = formData.to_dict()
        task = PointCloudService.fromFileObj(pointCloudId, file, metadata)
        return task

@api.route('/<int:projectId>/tasks/')
class ProjectTasksResource(Resource):

    @api.doc(id="getTasks",
             description="Get a listing of all the tasks of a project")
    @api.marshal_with(task)
    @project_permissions
    def get(self, projectId: int):
        from geoapi.models import Task
        from geoapi.db import db_session
        return db_session.query(Task).all()
