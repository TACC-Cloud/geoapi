from flask import request, abort
from flask_restx import Resource, Namespace, fields, inputs

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

def utc_datetime(value):
    dt = parser.parse(value)
    dt = dt.replace(tzinfo=tz.UTC)
    return dt


@api.route("/")
class Notifcations(Resource):
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
