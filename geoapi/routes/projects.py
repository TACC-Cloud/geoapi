from flask import request
from flask_restplus import Resource, Namespace, fields
from werkzeug.datastructures import FileStorage

from geoapi.models import Project, Feature, User
from geoapi.db import db_session
from geoapi.utils.decorators import jwt_decoder, project_permissions, project_feature_exists
from geoapi.services.projects import ProjectsService
from geoapi.services.users import UserService
from geoapi.services.features import FeaturesService
from geoapi.schemas import FeatureCollectionSchema, FeatureSchema

api = Namespace('projects', decorators=[jwt_decoder])

geojson = api.model('GeoJSON', {
    "type": fields.String(required=True),
    "geometry": fields.Raw(required=True),
    "properties": fields.Raw()
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

feature_schema = api.schema_model('Feature', FeatureSchema)


@api.route('/')
class ProjectsListing(Resource):

    @api.doc(id="getProjects",
             description='Get a listing of projects')
    @api.marshal_with(project)
    def get(self):
        u = request.current_user
        return ProjectsService.list(username=u.username)

    @api.doc(id="createProject",
             description='Create a new project')
    @api.expect(project)
    @api.marshal_with(project)
    def post(self):
        u = request.current_user
        return ProjectsService.create(api.payload, u)


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
             description="Add a user to the project")
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
        return ProjectsService.removeUserFromProject(projectId)



@api.route('/<int:projectId>/features/')
class ProjectFeaturesResource(Resource):

    @api.doc(id="getFeatures",
             description="GET all the features of a project as GeoJSON")
    @project_permissions
    def get(self, projectId: int):
        query = request.args
        return ProjectsService.getFeatures(projectId, query)

    @api.doc(id="addGeoJSONFeature",
             description="Add a GeoJSON feature to a project")
    @api.expect(feature_schema)
    @project_permissions
    def post(self, projectId: int):
        return FeaturesService.addGeoJSON(projectId, request.json)

@api.route('/<int:projectId>/features/<int:featureId>/properties/')
class ProjectFeaturePropertiesResource(Resource):

    @api.doc(id="updateFeatureProperties",
             description="Update the properties of a feature")
    @project_permissions
    @project_feature_exists
    def post(self, projectId: int, featureId: int):
        return FeaturesService.setProperties(featureId, request.json)

@api.route('/<int:projectId>/features/files/')
class ProjectFeaturesFilesResource(Resource):

    @api.doc(id="uploadFile",
             description='Add a new feature to a project. Can upload a file '
             '(georeferenced image, shapefile, lidar (las, lsz))')
    @project_permissions
    def post(self, projectId: int):
        file = request.files['file']
        formData = request.form
        metadata = formData.to_dict()
        FeaturesService.fromImage(projectId, file, metadata)


file_upload_parser = api.parser()
file_upload_parser.add_argument('file', location='files', type=FileStorage, required=True)

@api.route('/<int:projectId>/features/<int:featureId>/assets/')
class ProjectFeaturesCollectionResource(Resource):

    @api.doc(id="addFeatureAsset",
             description='Add a static asset to a collection. Must be an image at the moment')
    @api.expect(file_upload_parser)
    @project_permissions
    @project_feature_exists
    def post(self, projectId: int, featureId: int) -> None:
        args = file_upload_parser.parse_args()
        FeaturesService.createFeatureAsset(projectId, featureId, args['file'])








