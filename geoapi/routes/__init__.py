from flask_restx import Api
from .projects import api as projects
from .status import api as status
from .streetview import api as streetview
from .notifications import api as notifications
from .auth import api as auth

api = Api(
    title="GeoAPI",
    version="0.2",
    description="Geospatial API for TAPIS",
    security=["JWT"],
    authorizations={"JWT": {"type": "apiKey", "name": "X-Tapis-Token", "in": "header"}},
)

api.add_namespace(projects)
api.add_namespace(notifications)
api.add_namespace(status)
api.add_namespace(streetview)
api.add_namespace(auth)
