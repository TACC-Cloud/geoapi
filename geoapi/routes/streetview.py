from geoapi.services.streetview import StreetviewService
from geoapi.tasks import streetview
from geoapi.log import logging
from geoapi.exceptions import ApiException, StreetviewAuthException, StreetviewLimitException
from geoapi.utils.decorators import jwt_decoder
from flask_restplus import Namespace, Resource, fields
from flask_restplus.marshalling import marshal_with
from flask import request, abort
import uuid

from sqlalchemy.sql.functions import current_user

logger = logging.getLogger(__name__)

api = Namespace('streetview', decorators=[jwt_decoder])

streetview_params = api.model('StreetviewParams', {
    'service': fields.String(required=False),
    'service_user': fields.String(required=False),
    'token': fields.String(required=False)
})

default_response = api.model('DefaultAgaveResponse', {
    "message": fields.String(),
    "version": fields.String(),
    "status": fields.String(default="success")
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
    'sequence_id': fields.String(required=False)
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

@api.route('/')
class StreetviewListing(Resource):
    @api.doc(id="getStreetviews",
             description="Get all streetviews for a user")
    @api.marshal_with(streetview_service, as_list=True)
    def get(self):
        u = request.current_user
        logger.info("Get all streetview objects user:{}".format(u.username))
        return StreetviewService.list(u)

    @api.doc(id="createStreetview",
             description="Create streetview for a user")
    @api.expect(streetview_params)
    @api.marshal_with(streetview_service)
    def post(self):
        u = request.current_user
        service = api.payload.get('service')
        logger.info("Create streetview object for user:{} and service:{}".format(u.username, service))
        return StreetviewService.create(u, api.payload)


@api.route('/<int:streetview_id>/')
class StreetviewResource(Resource):
    @api.doc(id="getStreetview",
             description="Get a streetview object")
    @api.marshal_with(streetview_service)
    def get(self, streetview_id: int):
        u = request.current_user
        logger.info("Get streetview object of id:{} for user:{}".format(streetview_id, u.username))
        return StreetviewService.get(streetview_id)

    @api.doc(id="deleteStreetview",
             description="Delete a streetview object")
    def delete(self, streetview_id: int):
        u = request.current_user
        logger.info("Delete streetview object of id:{} for user:{}".format(streetview_id, u.username))
        return StreetviewService.delete(streetview_id)

    @api.doc(id="updateStreetview",
             description="Update streetview for a user")
    @api.expect(streetview_params)
    @api.marshal_with(streetview_service)
    def put(self, streetview_id: int):
        u = request.current_user
        logger.info("Update streetview object id:{} user:{}".format(streetview_id, u.username))
        return StreetviewService.update(streetview_id, api.payload)


@api.route('/<service>/')
class StreetviewServiceResource(Resource):
    @api.doc(id="getStreetviewByService",
             description="Get a streetview object by service name")
    @api.marshal_with(streetview_service)
    def get(self, service: str):
        u = request.current_user
        logger.info("Get streetview object for service:{} for user:{}".format(service, u.username))
        return StreetviewService.getByService(u, service)

    @api.doc(id="deleteStreetviewByService",
             description="Delete a streetview object by service name")
    def delete(self, service: str):
        u = request.current_user
        logger.info("Delete streetview object for service:{} for user:{}".format(service, u.username))
        return StreetviewService.deleteByService(u, service)

    @api.doc(id="updateStreetviewByService",
             description="Update streetview for a user by service name")
    @api.expect(streetview_params)
    @api.marshal_with(streetview_service)
    def put(self, service: str):
        u = request.current_user
        logger.info("Update streetview object for service:{} user:{}".format(service, u.username))
        return StreetviewService.updateByService(u, service, api.payload)


@api.route('/<streetview_id>/organization/')
class StreetviewOrganizationsResource(Resource):
    @api.doc(id="getStreetviewOrganizations",
             description="Get organizations from streetview object")
    @api.marshal_with(streetview_organization)
    def get(self, streetview_id: int):
        u = request.current_user
        logger.info("Get streetview organizations from streetview object for user:{}"
                    .format(u.username))
        return StreetviewService.getAllOrganizations(streetview_id)

    @api.doc(id="createStreetviewOrganizations",
             description="Create organizations for a streetview object")
    @api.expect(streetview_organization)
    @api.marshal_with(streetview_organization)
    def post(self, streetview_id: int):
        u = request.current_user
        logger.info("Create streetview organization for a streetview object for user:{}"
                    .format(u.username))
        return StreetviewService.createOrganization(streetview_id, api.payload)


@api.route('/organization/<organization_key>/')
class StreetviewOrganizationResource(Resource):
    @api.doc(id="deleteStreetviewOrganization",
             description="Delete organization from streetview object")
    def delete(self, organization_key: int):
        u = request.current_user
        logger.info("Delete streetview organization from streetview object for user:{}"
                    .format(u.username))
        StreetviewService.deleteOrganization(organization_key)

    @api.doc(id="updateStreetviewOrganization",
             description="Update organization from streetview object")
    @api.expect(streetview_organization)
    def put(self, organization_key: int):
        u = request.current_user
        logger.info("Update streetview organization in streetview object for user:{}"
                    .format(u.username))
        return StreetviewService.updateOrganization(organization_key, api.payload)


@api.route('/instances/<instance_id>/')
class StreetviewInstanceResource(Resource):
    @api.doc(id="deleteStreetviewInstance",
             description="Delete streetview instance")
    def delete(self, instance_id: int):
        u = request.current_user
        payload = request.json
        logger.info("Delete streetview instance for user:{}"
                    .format(u.username))
        StreetviewService.deleteInstance(instance_id)


@api.route('/sequences/')
class StreetviewSequencesResource(Resource):
    @api.doc(id="addStreetviewSequence",
             description="Add sequences to streetview instance")
    def post(self):
        u = request.current_user
        payload = request.json
        logger.info("Add streetview sequence to streetview instance for user:{}"
                    .format(u.username))
        StreetviewService.addSequenceToInstance(u, payload)


@api.route('/sequences/<sequence_id>/')
class StreetviewSequenceResource(Resource):
    @api.doc(id="getStreetviewSequence",
             description="Get a streetview service's sequence")
    @marshal_with(streetview_sequence)
    def get(self, sequence_id: str):
        u = request.current_user
        logger.info("Get streetview sequence of id:{} for user:{}".format(sequence_id, u.username))
        return StreetviewService.getSequenceFromId(sequence_id)

    @api.doc(id="deleteStreetviewSequence",
             description="Delete a streetview service's sequence")
    def delete(self, sequence_id: int):
        u = request.current_user
        logger.info("Delete streetview sequence of id:{} for user:{}".format(sequence_id, u.username))
        StreetviewService.deleteSequence(sequence_id)

    @api.doc(id="updateStreetviewSequence",
             description="Update a streetview service's sequence")
    @api.expect(streetview_organization)
    @marshal_with(streetview_sequence)
    def put(self, sequence_id: int):
        u = request.current_user
        logger.info("Update streetview sequence of id:{} for user:{}".format(sequence_id, u.username))
        return StreetviewService.updateSequence(sequence_id, api.payload)


@api.route('/upload/')
class StreetviewUploadFilesResource(Resource):
    @api.doc(id="uploadFilesToStreetview",
             description='Import all files in a directory into a project from Tapis. The files should '
                         'contain GPano metadata for compatibility with streetview services. This'
                         'is an asynchronous operation, files will be imported in the background'
             )
    @api.expect(streetview_folder_import)
    @api.marshal_with(ok_response)
    def post(self):
        u = request.current_user
        logger.info("Upload images to streetview for user:{}".format(u.username))
        try:
            streetview.upload(u, api.payload)
        except StreetviewAuthException as e:
            abort(401, e)
        except StreetviewLimitException as e:
            abort(403, e)
        return {"message": "accepted"}
