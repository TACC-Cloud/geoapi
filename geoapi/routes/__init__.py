from flask_restplus import Api
from .projects import api as projects
from .auth import api as auth

api = Api(
    title='GeoAPI',
    version='0.1',
    description='Description',
)

api.add_namespace(projects)
api.add_namespace(auth)