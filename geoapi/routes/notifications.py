from flask import request, abort
from flask_restplus import Resource, Namespace, fields, inputs

from geoapi.log import logging
from geoapi.utils.decorators import jwt_decoder
from geoapi.services.notifications import NotificationsService

logger = logging.getLogger(__name__)

api = Namespace('notifications', decorators=[jwt_decoder])

notification_response = api.model('NotificationResponse', {
    "status": fields.String(),
    "message": fields.String(),
    "created": fields.DateTime(),
    "viewed": fields.Boolean(),
    "id": fields.Integer()
})

@api.route("/")
class Notifcations(Resource):

    @api.doc(id="get",
             description='Get a list of notifications')
    @api.marshal_with(notification_response, as_list=True)
    def get(self):
        u = request.current_user
        return NotificationsService.getAll(u)
