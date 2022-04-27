from flask import request, abort
from flask_restplus import Resource, Namespace, fields, inputs

from geoapi.log import logging
from geoapi.utils.decorators import jwt_decoder, not_anonymous
from geoapi.services.notifications import NotificationsService
from dateutil import parser, tz

logger = logging.getLogger(__name__)

api = Namespace('notifications', decorators=[jwt_decoder])

notification_response = api.model('NotificationResponse', {
    "status": fields.String(),
    "message": fields.String(),
    "created": fields.DateTime(),
    "viewed": fields.Boolean(),
    "id": fields.Integer()
})

progress_notification_response = api.model('ProgressNotificationResponse', {
    "status": fields.String(),
    "message": fields.String(),
    "progress": fields.Integer(),
    "uuid": fields.String(),
    "created": fields.DateTime(),
    "viewed": fields.Boolean(),
    "id": fields.Integer(),
    "logs": fields.Raw()
})

ok_response = api.model('OkResponse', {
    "message": fields.String(default="accepted")
})

def utc_datetime(value):
    dt = parser.parse(value)
    dt = dt.replace(tzinfo=tz.UTC)
    return dt


@api.route("/")
class Notifications(Resource):
    parser = api.parser()
    parser.add_argument('startDate', location='args', type=utc_datetime,
                        help="Only return notifications created more recently than startDate")
    @api.doc(id="get",
             description='Get a list of notifications')
    @api.marshal_with(notification_response, as_list=True)
    @not_anonymous
    def get(self):
        query = self.parser.parse_args()
        u = request.current_user
        return NotificationsService.get(u, query)


@api.route("/progress")
class ProgressNotifications(Resource):
    @api.doc(id="get",
             description='Get a list of progress notifications')
    @api.marshal_with(progress_notification_response, as_list=True)
    def get(self):
        u = request.current_user
        return NotificationsService.getProgress(u)

    @api.doc(id="delete",
             description='Delete all done progress notifications')
    @api.marshal_with(ok_response)
    def delete(self):
        return NotificationsService.deleteAllDoneProgress()


@api.route("/progress/<string:progressUUID>")
class ProgressNotificationResource(Resource):
    @api.doc(id="get",
             description='Get a specific progress notification')
    @api.marshal_with(progress_notification_response)
    def get(self, progressUUID):
        return NotificationsService.getProgressUUID(progressUUID)

    @api.doc(id="delete",
             description='Delete a specific progress notification')
    @api.marshal_with(ok_response)
    def delete(self, progressUUID):
        return NotificationsService.deleteProgress(progressUUID)
