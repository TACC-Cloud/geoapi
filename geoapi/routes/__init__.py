from flask_restplus import Api
from .projects import api as projects

api = Api(
    title='GeoAPI',
    version='0.1',
    description='Geospatial API for TAPIS',
    security=['Token', 'JWT'],
    authorizations={
        'Token': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        },
        'JWT': {
            'type': 'apiKey',
            'name': 'X-JWT-Assertion-designsafe',
            'in': 'header'
        }
    }
)

api.add_namespace(projects)

