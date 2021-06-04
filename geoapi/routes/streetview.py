from geoapi.services.streetview import StreetviewService
from geoapi.tasks import streetview
from geoapi.log import logging
from geoapi.exceptions import ApiException
from geoapi.utils.decorators import jwt_decoder
from flask_restplus import Namespace, Resource, fields
from flask_restplus.marshalling import marshal_with
from flask import request, abort
import uuid

from sqlalchemy.sql.functions import current_user

logger = logging.getLogger(__name__)

api = Namespace('streetview', decorators=[jwt_decoder])

project = api.model('Project', {
    'id': fields.Integer(),
    'name': fields.String(required=True),
    'description': fields.String(required=False),
    'public': fields.Boolean(required=False),
    'uuid': fields.String()
})

streetview_token = api.model('StreetviewToken', {
    'token': fields.String()
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
    'folder': fields.Nested(tapis_file),
    'mapillary': fields.Boolean(),
    'google': fields.Boolean(),
    'organization': fields.String(),
    'retry': fields.Boolean()
})

streetview_sequence = api.model('StreetviewSequence', {
    'id': fields.Integer(),
    'streetview_id': fields.Integer(),
    'service': fields.String(),
    'start_date': fields.DateTime(dt_format='rfc822', required=False),
    'end_date': fields.DateTime(dt_format='rfc822', required=False),
    'bbox': fields.String(required=False),
    'sequence_key': fields.String(required=False),
    'organization_key': fields.String(required=False),
})

streetview_object = api.model('Streetview', {
    'id': fields.Integer(),
    'user_id': fields.Integer(),
    'path': fields.String(),
    'system_id': fields.String(),
    'sequences': fields.List(fields.Nested(streetview_sequence), allow_null=True),
    'projects':  fields.List(fields.Nested(project), allow_null=True)
})


@api.route('/')
class StreetviewListing(Resource):
    @api.doc(id="getStreetviews",
             description="Get all streetview for a user")
    @api.marshal_with(streetview_object, as_list=True)
    def get(self):
        u = request.current_user
        logger.info("Get all streetview objects user:{}".format(u.username))
        return StreetviewService.getAll(u)


@api.route('/<streetview_id>/')
class StreetviewResource(Resource):
    @api.doc(id="getStreetview",
             description="Get a streetview object")
    @api.marshal_with(streetview_object)
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


@api.route('/sequences/')
class StreetviewSequencesResource(Resource):
    @api.doc(id="addStreetviewSequences",
             description="Add sequences to streetview objects")
    def post(self):
        u = request.current_user
        payload = request.json
        logger.info("Add streetview sequences to streetview object for user:{}"
                    .format(u.username))
        StreetviewService.addSequenceToStreetview(u, payload)


@api.route('/sequences/<sequence_id>/')
class StreetviewSequenceResource(Resource):
    @api.doc(id="deleteStreetviewSequence",
             description="Get a streetview service's sequences")
    def delete(self, sequence_id: int):
        u = request.current_user
        logger.info("Delete streetview sequence of id:{} for user:{}".format(sequence_id, u.username))
        StreetviewService.deleteSequence(sequence_id)

    @api.doc(id="updateStreetviewSequence",
             description="Update a streetview service's sequences")
    @marshal_with(streetview_sequence)
    def put(self, sequence_id: int):
        u = request.current_user
        logger.info("Update streetview sequence of id:{} for user:{}".format(sequence_id, u.username))
        return StreetviewService.updateSequence(sequence_id, api.payload)


@api.route('/sequences/notifications/<task_uuid>/')
class StreetviewSession(Resource):
    @api.doc(id="deleteStreetviewSession",
             description="Delete a streetview upload session")
    def delete(self, task_uuid: str):
        u = request.current_user
        logger.info("Delete upload progress for streetview upload session {} for user:{}"
                    .format(task_uuid, u.username))
        param_uuid = uuid.UUID(task_uuid)
        streetview.delete_upload_session(u, param_uuid)

    @api.doc(id="createStreetviewSession",
             description="Create a streetview upload session")
    def post(self, task_uuid: str):
        u = request.current_user
        logger.info("Create upload progress for streetview upload session {} for user:{}"
                    .format(task_uuid, u.username))
        param_uuid = uuid.UUID(task_uuid)
        streetview.create_upload_session(u, param_uuid)


@api.route('/<service>/token/')
class StreetviewTokenResource(Resource):
    @api.doc(id="deleteStreetviewToken",
             description="Remove the streetview server token for a user")
    def delete(self, service: str):
        u = request.current_user
        logger.info("Delete token for streetview service for user:{}".format(u.username))
        StreetviewService.deleteToken(u,
                                      service)

    @api.doc(id="setStreetviewToken",
             description="Set the streetview server token for a user")
    @api.expect(streetview_token)
    def post(self, service: str):
        u = request.current_user
        logger.info("Set token for streetview service for user:{}".format(u.username))
        payload = request.json
        StreetviewService.setToken(u,
                                   service,
                                   payload['token'])


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
        except ApiException:
            abort(403, "Access denied")
        return {"message": "accepted"}
