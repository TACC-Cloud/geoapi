from geoapi.services.streetview import StreetviewService
from geoapi.tasks import streetview
from geoapi.log import logging
from geoapi.utils.decorators import jwt_decoder
from geoapi.db import db_session
from flask_restx import Namespace, Resource, fields
from flask_restx.marshalling import marshal_with
from flask import request


logger = logging.getLogger(__name__)

api = Namespace('streetview', decorators=[jwt_decoder])

streetview_service_resource_param = api.model('StreetviewParams', {
    'service': fields.String(required=False),
    'service_user': fields.String(required=False),
    'token': fields.String(required=False)
})

ok_response = api.model('OkResponse', {
    "message": fields.String(default="accepted")
})

tapis_file = api.model('TapisFile', {
    'system': fields.String(required=True),
    'path': fields.String(required=True)
})

streetview_folder_import = api.model('TapisFolderImport', {
    'service': fields.Nested(tapis_file),
    'system_id': fields.String(),
    'path': fields.String()
})

streetview_sequence = api.model('StreetviewSequence', {
    'id': fields.Integer(),
    'streetview_instance_id': fields.Integer(),
    'start_date': fields.DateTime(dt_format='rfc822', required=False),
    'end_date': fields.DateTime(dt_format='rfc822', required=False),
    'bbox': fields.String(required=False),
    'sequence_id': fields.String(required=False),
    'organization_id': fields.String(required=False)
})

streetview_organization = api.model('StreetviewOrganization', {
    'id': fields.Integer(required=False),
    'streetview_id': fields.Integer(required=False),
    'name': fields.String(),
    'slug': fields.String(),
    'key': fields.String()
})

streetview_instance = api.model('StreetviewInstance', {
    'id': fields.Integer(),
    'streetview_id': fields.Integer(),
    'system_id': fields.String(),
    'path': fields.String(),
    'sequences': fields.List(fields.Nested(streetview_sequence), allow_null=True),
})

streetview_service = api.model('Streetview', {
    'id': fields.Integer(),
    'user_id': fields.Integer(),
    'token': fields.String(),
    'service': fields.String(),
    'service_user': fields.String(),
    'organizations': fields.List(fields.Nested(streetview_organization), allow_null=True),
    'instances': fields.List(fields.Nested(streetview_instance), allow_null=True)
})


@api.route('/services/')
class StreetviewServiceResources(Resource):
    @api.doc(id="getStreetviewServiceResources",
             description="Get all streetview service objects for a user")
    @api.marshal_with(streetview_service, as_list=True)
    def get(self):
        u = request.current_user
        logger.info("Get all streetview objects user:{}".format(u.username))
        return StreetviewService.list(db_session, u)

    @api.doc(id="createStreetviewServiceResource",
             description="Create streetview service object for a user")
    @api.expect(streetview_service_resource_param)
    @api.marshal_with(streetview_service)
    def post(self):
        u = request.current_user
        service = api.payload.get('service')
        logger.info("Create streetview object for user:{} and service:{}".format(u.username, service))
        return StreetviewService.create(db_session, u, api.payload)


@api.route('/services/<service>/')
class StreetviewServiceResource(Resource):
    @api.doc(id="getStreetviewServiceResource",
             description="Get a streetview service resource by service name")
    @api.marshal_with(streetview_service)
    def get(self, service: str):
        u = request.current_user
        logger.info("Get streetview service object for service:{} for user:{}".format(service, u.username))
        return StreetviewService.getByService(db_session, u, service)

    @api.doc(id="deleteStreetviewServiceResource",
             description="Delete a streetview service resource by service name")
    def delete(self, service: str):
        u = request.current_user
        logger.info("Delete streetview object for service:{} for user:{}".format(service, u.username))
        return StreetviewService.deleteByService(db_session, u, service)

    @api.doc(id="updateStreetviewServiceResource",
             description="Update streetview service resource for a user by service name")
    @api.expect(streetview_service_resource_param)
    @api.marshal_with(streetview_service)
    def put(self, service: str):
        u = request.current_user
        logger.info("Update streetview service resource for service:{} user:{}".format(service, u.username))
        return StreetviewService.updateByService(db_session, u, service, api.payload)


@api.route('/services/<service>/organization/')
class StreetviewOrganizationsResource(Resource):
    @api.doc(id="getStreetviewOrganizations",
             description="Get organizations from streetview service resource")
    @api.marshal_with(streetview_organization)
    def get(self, service: str):
        u = request.current_user
        logger.info("Get streetview organizations from streetview service resource for user:{}"
                    .format(u.username))
        return StreetviewService.getAllOrganizations(db_session, u, service)

    @api.doc(id="createStreetviewOrganizations",
             description="Create organizations for a streetview object")
    @api.expect(streetview_organization)
    @api.marshal_with(streetview_organization)
    def post(self, service: str):
        u = request.current_user
        logger.info("Create streetview organization for a streetview service resource for user:{}"
                    .format(u.username))
        return StreetviewService.createOrganization(db_session, u, service, api.payload)


@api.route('/services/<service>/organization/<organization_id>/')
class StreetviewOrganizationResource(Resource):
    @api.doc(id="deleteStreetviewOrganization",
             description="Delete organization from streetview service resource")
    def delete(self, service: str, organization_id: int):
        u = request.current_user
        logger.info("Delete streetview organization from streetview service resource for user:{} and streetview service: {}"
                    .format(u.username, service))
        StreetviewService.deleteOrganization(db_session, organization_id)

    @api.doc(id="updateStreetviewOrganization",
             description="Update organization from streetview service resource")
    @api.expect(streetview_organization)
    def put(self, service: str, organization_id: int):
        u = request.current_user
        logger.info("Update streetview organization in streetview service resource for user:{} and streetview servicde: {}"
                    .format(u.username, service))
        return StreetviewService.updateOrganization(db_session, organization_id, api.payload)


@api.route('/instances/<instance_id>/')
class StreetviewInstanceResource(Resource):
    @api.doc(id="deleteStreetviewInstance",
             description="Delete streetview instance")
    def delete(self, instance_id: int):
        u = request.current_user
        logger.info("Delete streetview instance for user:{}"
                    .format(u.username))
        StreetviewService.deleteInstance(db_session, instance_id)


@api.route('/sequences/')
class StreetviewSequencesResource(Resource):
    @api.doc(id="addStreetviewSequence",
             description="Add sequences to streetview instance")
    def post(self):
        u = request.current_user
        payload = request.json
        logger.info("Add streetview sequence to streetview instance for user:{}"
                    .format(u.username))
        StreetviewService.addSequenceToInstance(db_session, u, payload)


@api.route('/sequences/<sequence_id>/')
class StreetviewSequenceResource(Resource):
    @api.doc(id="getStreetviewSequence",
             description="Get a streetview service's sequence")
    @marshal_with(streetview_sequence)
    def get(self, sequence_id: str):
        u = request.current_user
        logger.info("Get streetview sequence of id:{} for user:{}".format(sequence_id, u.username))
        return StreetviewService.getSequenceFromId(db_session, sequence_id)

    @api.doc(id="deleteStreetviewSequence",
             description="Delete a streetview service's sequence")
    def delete(self, sequence_id: int):
        u = request.current_user
        logger.info("Delete streetview sequence of id:{} for user:{}".format(sequence_id, u.username))
        StreetviewService.deleteSequence(db_session, sequence_id)

    @api.doc(id="updateStreetviewSequence",
             description="Update a streetview service's sequence")
    @api.expect(streetview_organization)
    @marshal_with(streetview_sequence)
    def put(self, sequence_id: int):
        u = request.current_user
        logger.info("Update streetview sequence of id:{} for user:{}".format(sequence_id, u.username))
        return StreetviewService.updateSequence(db_session, db_session, sequence_id, api.payload)


@api.route('/publish/')
class StreetviewPublishFilesResource(Resource):
    @api.doc(id="publishFilesToStreetview",
             description='Import all files in a directory into a project from Tapis. The files should '
                         'contain GPano metadata for compatibility with streetview services. This'
                         'is an asynchronous operation, files will be imported in the background'
             )
    @api.expect(streetview_folder_import)
    @api.marshal_with(ok_response)
    def post(self):
        u = request.current_user
        logger.info("Publish images to streetview for user:{}".format(u.username))
        streetview.publish(db_session, u, api.payload)
        return {"message": "accepted"}
