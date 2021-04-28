from flask_restplus import Api
from .projects import api as projects
from .public_projects import api as public_projects
from .notifications import api as notifications
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
api.add_namespace(public_projects)
api.add_namespace(notifications)

