from flask_restplus import Resource, Namespace, fields
from geoapi.models import Project, LayerGroup, Feature, User
from geoapi.db import db_session
from geoapi.utils.decorators import jwt_decoder, project_permissions
from geoapi.dao.projects import ProjectsDAO
from geoapi.dao.users import UserDAO

api = Namespace('projects', decorators=[jwt_decoder])

layergroup = api.model('LayerGroup', {
    'name': fields.String(required=True),
    'description': fields.String(required=False)
})
project = api.model('Project', {
    'name': fields.String(required=True),
    'description': fields.String(required=False),
    'layergroups': fields.Nested(layergroup)
})



@api.route('/')
class ProjectsListing(Resource):

    @api.doc('Get a listing of proojects')
    @api.marshal_with(project)
    def get(self):
        return ProjectsDAO.list(username="jmeiring")

    @api.doc('Create a new project')
    @api.expect(project)
    @api.marshal_with(project)
    def post(self):
        u = UserDAO.getUser('jmeiring')
        return ProjectsDAO.create(api.payload, u)



@api.route('/<int:projectId>/')
class ProjectResource(Resource):

    @project_permissions
    def get(self, projectId: int):
        return ProjectsDAO.get(projectId)

    def delete(self, projecId):
        return True

    def put(self, projectId):
        return True

@api.route('/<int:projectId>/layergroups/')
class LayerGroupsResource(Resource):

    def get(self, projectId):
        return db_session.query(LayerGroup)\
            .filter().all()

    def delete(self, projecId):
        return True

    def put(self, projectId):
        return True

    def post(self, projectId):
        return True

@api.route('/<int:projecId>/layergroups/<int:layergroupId>/')
class LayerGroupResource(Resource):

    def get(self, projecId, layergroupId):
        return db_session.query(LayerGroup)\
            .filter().all()

    def delete(self, projecId):
        return True

    def put(self, projectId):
        return True


@api.route('/<int:projectId>/layergroups/<int:layergroupId>/features/')
class LayerGroupFeaturesResource(Resource):

    def get(self, projectId, layergroupId):
        return db_session.query(Feature)\
            .filter(Feature.layergroup_id == layergroupId)\
            .all()

    def delete(self, projecId):
        return True

    def put(self, projectId):
        return True

    def post(self, projecId, layergroupId):
        return True

@api.route('/<int:projectId>/layergroups/<int:layergroupId>/features/<int:featureId>/')
class LayerGroupFeatureResource(Resource):

    def get(self, projectId):
        return db_session.query(LayerGroup)\
            .filter().all()

    def delete(self, projecId):
        return True

    def put(self, projectId):
        return True
