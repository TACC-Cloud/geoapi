from flask_restx import Resource, Namespace, fields
import time
from geoapi.log import logging
from geoapi.utils.decorators import jwt_decoder, not_anonymous

logger = logging.getLogger(__name__)

api = Namespace('status', decorators=[jwt_decoder])

status_response = api.model('StatusResponse', {
    "status": fields.String(),
})


@api.route("/")
class Status(Resource):
    @api.doc(id="get",
             description='Get status')
    @api.marshal_with(status_response)
    @not_anonymous
    def get(self):
        time.sleep(1)
        return {"status": "OK"}
