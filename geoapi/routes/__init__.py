from flask_restplus import Api
from .projects import api as projects

api = Api(
    title='GeoAPI',
    version='0.1',
    description='Geospatial API for TAPIS',
    authorizations={
        'Oauth2': {
            'type': 'oauth2',
            'flow': 'implicit',
            'authorizationUrl': 'https://agave.designsafe-ci.org/authorize',
            'scopes': {
                'PRODUCTION': 'default scope for all tapis services'
            }
        },
        'Token': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        },
        'JWT': {
            'type': 'apiKey',
            'name': 'x-jwt-assertion-DEV',
            'in': 'header'
        }
    }
)

api.add_namespace(projects)

