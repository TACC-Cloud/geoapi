from litestar import Router

from .projects import projects_router
from .status import StatusController
from .streetview import StreetviewController
from .streetview_mapillary_auth import StreetviewMapillaryAuthController
from .notifications import NotificationsController
from .auth import AuthController


api_router = Router(
    path="/",
    route_handlers=[
        projects_router,
        NotificationsController,
        StatusController,
        StreetviewController,
        StreetviewMapillaryAuthController,
        AuthController,
    ],
)
