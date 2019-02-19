from flask import request
from flask_restplus import Resource, Namespace, fields
from geoapi.models import Project, LayerGroup, Feature, User
from geoapi.db import db_session
from geoapi.utils.decorators import jwt_decoder, project_permissions
from geoapi.dao.projects import ProjectsDAO
from geoapi.dao.users import UserDAO

api = Namespace('projects', decorators=[jwt_decoder])

layergroup = api.model('LayerGroup', {
    'id': fields.Integer(),
    'name': fields.String(required=True),
    'description': fields.String(required=False)
})
project = api.model('Project', {
    'id': fields.Integer(),
    'name': fields.String(required=True),
    'description': fields.String(required=False),
    'uuid': fields.String(),
    'layergroups': fields.Nested(layergroup)
})
user = api.model('User', {
    'id': fields.Integer(),
    'username': fields.String(required=True)
})


@api.route('/')
class ProjectsListing(Resource):

    @api.doc('Get a listing of projects')
    @api.marshal_with(project)
    def get(self):
        u = request.current_user
        return ProjectsDAO.list(username=u.username)

    @api.doc('Create a new project')
    @api.expect(project)
    @api.marshal_with(project)
    def post(self):
        u = request.current_user
        return ProjectsDAO.create(api.payload, u)


@api.route('/<int:projectId>/')
class ProjectResource(Resource):

    @api.marshal_with(project)
    @project_permissions
    def get(self, projectId: int):
        return ProjectsDAO.get(projectId)

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
        return ProjectsDAO.getUsers(projectId)

    @api.expect(user)
    @project_permissions
    def post(self, projectId: int):
        payload = request.json
        username = payload["username"]
        ProjectsDAO.addUserToProject(projectId, username)
        return "ok"

@api.route('/<int:projectId>/users/<username>/')
class ProjectUserResource(Resource):

    @project_permissions
    def delete(self, projectId: int):
        return ProjectsDAO.removeUserFromProject(projectId)

    @project_permissions
    def put(self, projectId: int):
        return True



@api.route('/<int:projectId>/layergroups/')
class LayerGroupsResource(Resource):

    @project_permissions
    def get(self, projectId):
        return db_session.query(LayerGroup)\
            .filter().all()

    @project_permissions
    def delete(self, projectId: int):
        return True

    @project_permissions
    def put(self, projectId: int):
        return True

    @project_permissions
    def post(self, projectId: int):
        return True


@api.route('/<int:projectId>/layergroups/<int:layergroupId>/')
class LayerGroupResource(Resource):

    @project_permissions
    def get(self, projecId, layergroupId):
        return db_session.query(LayerGroup)\
            .filter().all()

    @project_permissions
    def delete(self, projectId: int):
        return True

    @project_permissions
    def put(self, projectId: int):
        return True


@api.route('/<int:projectId>/layergroups/<int:layergroupId>/features/')
class LayerGroupFeaturesResource(Resource):

    @project_permissions
    def get(self, projectId, layergroupId):
        return db_session.query(Feature)\
            .filter(Feature.layergroup_id == layergroupId)\
            .all()

    @project_permissions
    def delete(self, projectId):
        return True

    @project_permissions
    def put(self, projectId):
        return True

    @project_permissions
    def post(self, projectId, layergroupId):
        return True


@api.route('/<int:projectId>/layergroups/<int:layergroupId>/features/<int:featureId>/')
class LayerGroupFeatureResource(Resource):

    @project_permissions
    def get(self, projectId: int):
        return db_session.query(LayerGroup)\
            .filter().all()

    @project_permissions
    def delete(self, projectId: int):
        return True

    @project_permissions
    def put(self, projectId: int):
        return True


@api.route('/<int:projectId>/layergroups/<int:layergroupId>/features/<int:featureId>/media/')
class LayerGroupFeatureMediaResource(Resource):

    @project_permissions
    def get(self, projectId: int, layergroupId: int, featureId: int):
        return True

    @project_permissions
    def delete(self, projectId: int):
        return True

    @project_permissions
    def put(self, projectId: int):
        return True

    @project_permissions
    def post(self, projectId: int):
        return True

