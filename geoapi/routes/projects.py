from flask import request
from flask_restplus import Resource, Namespace, fields
from werkzeug.datastructures import FileStorage

from geoapi.models import Project, Feature, User
from geoapi.db import db_session
from geoapi.utils.decorators import jwt_decoder, project_permissions
from geoapi.services.projects import ProjectsService
from geoapi.services.users import UserService
from geoapi.services.features import FeatureService
from geoapi.schemas import FeatureCollectionSchema, FeatureSchema

api = Namespace('projects', decorators=[jwt_decoder])

geojson = api.model('GeoJSON', {
    "type": fields.String(),
    "geometry": fields.Raw(),
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

    @api.doc('Get a listing of projects')
    @api.marshal_with(project)
    def get(self):
        u = request.current_user
        return ProjectsService.list(username=u.username)

    @api.doc('Create a new project')
    @api.expect(project)
    @api.marshal_with(project)
    def post(self):
        u = request.current_user
        return ProjectsService.create(api.payload, u)


@api.route('/<int:projectId>/')
class ProjectResource(Resource):

    @api.marshal_with(project)
    @project_permissions
    def get(self, projectId: int):
        return ProjectsService.get(projectId)

    @project_permissions
    def delete(self, projectId: int):
        return True

    @project_permissions
    def put(self, projectId: int):
        return True

@api.route('/<int:projectId>/users/')
class ProjectUsersResource(Resource):

    @api.marshal_with(user)
    @project_permissions
    def get(self, projectId: int):
        return ProjectsService.getUsers(projectId)

    @api.expect(user)
    @project_permissions
    def post(self, projectId: int):
        payload = request.json
        username = payload["username"]
        ProjectsService.addUserToProject(projectId, username)
        return "ok"


@api.route('/<int:projectId>/users/<username>/')
class ProjectUserResource(Resource):

    @project_permissions
    def delete(self, projectId: int):
        return ProjectsService.removeUserFromProject(projectId)



@api.route('/<int:projectId>/features/')
class ProjectFeaturesResource(Resource):

    @project_permissions
    def get(self, projectId: int):
        return ProjectsService.getFeatures(projectId)

    @api.doc('')
    @api.expect(feature_schema)
    @project_permissions
    def post(self, projectId: int):
        return ProjectsService.addGeoJSON(projectId, request.json)

@api.route('/<int:projectId>/features/<int:featureId>/properties/')
class ProjectFeaturePropertiesResource(Resource):

    @api.doc('')
    @project_permissions
    def post(self, projectId: int, featureId: int):
        return FeatureService.setProperties(featureId, request.json)



file_upload_parser = api.parser()
file_upload_parser.add_argument('file', location='files', type=FileStorage, required=True)

@api.route('/<int:projectId>/features/files/')
class ProjectFeaturesFilesResource(Resource):

    @api.doc('Add a new feature to a project. Can upload a file '
             '(GeoJSON, image, shapefile) or POST valid GeoJSON directly')
    @project_permissions
    def post(self, projectId: int):
        file = request.files['file']
        formData = request.form
        metadata = formData.to_dict()
        ProjectsService.addImage(projectId, file, metadata)


@api.route('/<int:projectId>/features/collection/')
class ProjectFeaturesCollectionResource(Resource):

    @api.doc('Create a special collection marker, which can have multiple static assets like images or videos attached to it')
    @api.expect(feature_schema)
    @project_permissions
    def post(self, projectId: int):
        args = feature_upload_parser.parse_args()
        if args.feature:
            ProjectsService.addGeoJSON(projectId, args.feature)


@api.route('/<int:projectId>/features/collection/<int:collectionId>')
class ProjectFeaturesCollectionResource(Resource):

    @api.doc('Add a static asset to a collection')
    @api.expect(file_upload_parser)
    @project_permissions
    def post(self, projectId: int, collectionId: int) -> None:
        args = file_upload_parser.parse_args()
        if args.file:
            ProjectsService.addGeoJSON(projectId, args.file)








