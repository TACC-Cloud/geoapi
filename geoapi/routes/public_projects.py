"""
This module provides public-projects route for use by guest users accessing
public projects.  This duplicates multiple GET routes in projects.py and
allows us to provide access to guests (via WSO2 configuration for guests:
`auth-type=None`). See https://jira.tacc.utexas.edu/browse/DES-1946 for
more details.
 """

from flask_restx import Namespace
from flask.views import MethodView
from geoapi.utils.decorators import jwt_decoder
from geoapi.log import logging
from geoapi.routes.projects import (ProjectFeatureAssetSourceResource, ProjectsListing, ProjectResource,
                                    ProjectFeaturesResource, ProjectFeatureResource,
                                    ProjectOverlaysResource, ProjectPointCloudResource,
                                    ProjectPointCloudsResource, ProjectTileServersResource)

logger = logging.getLogger(__name__)

api = Namespace('public-projects', decorators=[jwt_decoder])


class HideNonPublicMeta(type(MethodView)):
    """ Metaclass to limit the `methods` (defined in MethodViewType) to just GET """
    def __init__(cls, name, bases, d):
        super().__init__(name, bases, d)
        # provide only GET so that our view no longer provides any potentially
        # defined PUT, POST, PATCH, DELETE methods
        cls.methods = ["GET"]


@api.route('/')
class PublicProjectsListing(ProjectsListing, metaclass=HideNonPublicMeta):
    pass


@api.route('/<int:projectId>/')
class PublicProjectResource(ProjectResource, metaclass=HideNonPublicMeta):
    pass


@api.route('/<int:projectId>/features/')
class PublicProjectFeaturesResource(ProjectFeaturesResource, metaclass=HideNonPublicMeta):
    pass


@api.route('/<int:projectId>/features/<int:featureId>/')
class PublicProjectFeatureResource(ProjectFeatureResource, metaclass=HideNonPublicMeta):
    pass


@api.route('/<int:projectId>/overlays/')
class PublicProjectOverlaysResource(ProjectOverlaysResource, metaclass=HideNonPublicMeta):
    pass


@api.route('/<int:projectId>/point-cloud/')
class PublicProjectPointCloudsResource(ProjectPointCloudsResource, metaclass=HideNonPublicMeta):
    pass


@api.route('/<int:projectId>/point-cloud/<int:pointCloudId>/')
class PublicProjectPointCloudResource(ProjectPointCloudResource, metaclass=HideNonPublicMeta):
    pass


@api.route('/<int:projectId>/tile-servers/')
class PublicProjectTileServersResource(ProjectTileServersResource, metaclass=HideNonPublicMeta):
    pass
