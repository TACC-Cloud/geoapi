from flask_restx import Api
from .projects import api as projects
from .streetview import api as streetview
from .notifications import api as notifications
from .public_projects import api as public_projects

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
api.add_namespace(streetview)
