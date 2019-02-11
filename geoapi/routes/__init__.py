from flask_restplus import Api
from .projects import api as projects

api = Api(
    title='GeoAPI',
    version='0.1',
    description='Description',
)

api.add_namespace(projects)
