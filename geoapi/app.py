"""GeoAPI Application Module"""

from typing import Any, TYPE_CHECKING
from os import urandom
from litestar import Litestar, Request, Response, status_codes
from litestar.config.csrf import CSRFConfig
from litestar.logging.config import LoggingConfig
from litestar.middleware.logging import LoggingMiddlewareConfig
from litestar.middleware.session.server_side import (
    ServerSideSessionConfig,
    ServerSideSessionBackend,
)
from litestar.middleware.session.client_side import CookieBackendConfig
from litestar.openapi.config import OpenAPIConfig
from litestar.stores.redis import RedisStore
from litestar.stores.registry import StoreRegistry
from litestar.stores.memory import MemoryStore
from litestar.exceptions import InternalServerException
from litestar.connection import ASGIConnection
from litestar.security.jwt import JWTAuth
from litestar.security.session_auth import SessionAuth
from litestar.plugins.sqlalchemy import SQLAlchemyPlugin
from litestar.channels import ChannelsPlugin
from litestar.channels.backends.redis import RedisChannelsPubSubBackend
from litestar.channels.backends.memory import MemoryChannelsBackend
from litestar.types import Empty
from redis.asyncio import Redis
from geoapi.models import User
from geoapi.routes import api_router
from geoapi.settings import settings
from geoapi.db import (
    get_db_connection,
    close_db_connection,
    sqlalchemy_config,
)
from geoapi.exceptions import (
    InvalidGeoJSON,
    InvalidEXIFData,
    InvalidCoordinateReferenceSystem,
    ProjectSystemPathWatchFilesAlreadyExists,
    ApiException,
    StreetviewAuthException,
    StreetviewLimitException,
    AuthenticationIssue,
)
from geoapi.services.users import UserService
from geoapi.utils.users import AnonymousUser
from geoapi.utils.jwt_utils import get_pub_key, PUBLIC_KEY_FOR_TESTING
from geoapi.middleware import (
    GeoAPISessionAuthMiddleware,
    GeoAPIJWTAuthMiddleware,
    GeoAPIToken,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Exception handlers for Litestar
def geojson_exception_handler(request: Request, exc: InvalidGeoJSON) -> Response:
    """
    Handles exceptions related to invalid GeoJSON data."""
    return Response(
        content={"status": "error", "version": "0.1", "message": str(exc)},
        status_code=status_codes.HTTP_400_BAD_REQUEST,
    )


def api_exception_handler(request: Request, exc: ApiException) -> Response:
    """
    Handles exceptions related to API errors."""
    return Response(
        content={"status": "error", "version": "0.1", "message": str(exc)},
        status_code=status_codes.HTTP_400_BAD_REQUEST,
    )


def exif_exception_handler(request: Request, exc: InvalidEXIFData) -> Response:
    """
    Handles exceptions related to invalid EXIF data."""
    return Response(
        content={"message": "Invalid EXIF data, geolocation could not be found"},
        status_code=status_codes.HTTP_400_BAD_REQUEST,
    )


def coordinate_reference_system_exception_handler(
    request: Request, exc: InvalidCoordinateReferenceSystem
) -> Response:
    """
    Handles exceptions related to invalid coordinate reference systems."""
    return Response(
        content={
            "message": "Invalid data, coordinate reference system could not be found"
        },
        status_code=status_codes.HTTP_400_BAD_REQUEST,
    )


def project_system_path_watch_files_already_exists_handler(
    request: Request, exc: ProjectSystemPathWatchFilesAlreadyExists
) -> Response:
    """
    Handles exceptions when a project is already watching files for a specific storage system/path.
    """
    return Response(
        content={
            "message": "Conflict, a project watching files for this storage system/path already exists"
        },
        status_code=status_codes.HTTP_409_CONFLICT,
    )


def streetview_auth_exception_handler(
    request: Request, exc: StreetviewAuthException
) -> Response:
    """
    Handles exceptions related to authentication issues with the streetview service."""
    return Response(
        content={"message": "Not logged in to streetview service"},
        status_code=status_codes.HTTP_401_UNAUTHORIZED,
    )


def streetview_limit_exception_handler(
    request: Request, exc: StreetviewLimitException
) -> Response:
    """
    Handles exceptions related to exceeding the concurrent streetview publish limit."""
    return Response(
        content={"message": "Exceed concurrent streetview publish limit"},
        status_code=status_codes.HTTP_403_FORBIDDEN,
    )


def authentication_issue_exception_handler(
    request: Request, exc: AuthenticationIssue
) -> Response:
    """
    Handles general authentication issues."""
    return Response(
        content={"message": exc.message},
        status_code=status_codes.HTTP_400_BAD_REQUEST,
    )


# Handlers for user retrieval in JWT and session authentication
async def retrieve_jwt_user_handler(
    token: GeoAPIToken,
    connection: ASGIConnection[Any, Any, Any, Any],
) -> User | AnonymousUser:
    """Used by the JWTAuth Middleware to retrieve the user from the JWT token."""

    db_session: "Session" = sqlalchemy_config.provide_session(
        connection.app.state, connection.scope
    )

    # If no token, check for guest UUID
    if not token:
        # if JWT is not provided in header/cookie, then this is a guest user
        # and if hazmapper/taggit, a guest uuid is provided in the header
        guest_uuid = connection.headers.get("X-Guest-UUID")
        user = AnonymousUser(guest_unique_id=guest_uuid)
    else:
        try:
            username = token.extras["tapis/username"]
            tenant = token.extras["tapis/tenant_id"]
        except Exception as e:
            raise InternalServerException(
                f"There is an issue decoding the JWT: {e}"
            ) from e

        user = UserService.getUser(db_session, username, tenant)
        if not user:
            user = UserService.create(
                db_session, username=username, access_token=token, tenant=tenant
            )
        else:
            # Update the jwt access token
            #   (It is more common that user will be using an auth flow where hazmapper will auth
            #   with geoapi to get the token. BUT we can't assume that as it is also possible that
            #   user just uses geoapi as a service with token generated somewhere else. So we need
            #   to get/update just their access token for these cases)
            UserService.update_access_token(db_session, user, token.token)
    return user


async def retrieve_session_user_handler(
    session: dict[str, Any],
    connection: ASGIConnection[Any, Any, Any, Any],
) -> User | AnonymousUser:
    """Used by the SessionAuth Middleware to retrieve the user from the session."""
    db_session = sqlalchemy_config.provide_session(
        connection.app.state, connection.scope
    )

    if session is Empty or not session:
        return AnonymousUser()

    username = session.get("username")
    tenant = session.get("tenant")
    return UserService.getUser(
        database_session=db_session, username=username, tenant=tenant
    )


# Litestar application configuration
if settings.TESTING:
    root_store = MemoryStore()
    session_auth_config = ServerSideSessionConfig(store=root_store)
    stores = None
    csrf_config = None
    channels = ChannelsPlugin(
        backend=MemoryChannelsBackend(),
        arbitrary_channels_allowed=True,
    )
else:
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
    root_store = RedisStore.with_client(url=redis_url)
    session_auth_config = ServerSideSessionConfig(httponly=False, secure=True)
    stores = StoreRegistry(default_factory=root_store.with_namespace)
    csrf_config = CSRFConfig(secret=settings.SECRET_KEY, exclude=["/api/webhooks"])
    channels = ChannelsPlugin(
        backend=RedisChannelsPubSubBackend(redis=Redis.from_url(redis_url)),
        arbitrary_channels_allowed=True,
    )

session_auth = SessionAuth["User", ServerSideSessionBackend](
    retrieve_user_handler=retrieve_session_user_handler,
    session_backend_config=session_auth_config,
    exclude=[
        "/auth/login",
        "/auth/callback",
        "/schema",
        "/streetview/auth/mapillary/login",
        "/streetview/auth/mapillary/callback",
    ],
    authentication_middleware_class=GeoAPISessionAuthMiddleware,
)

jwt_auth = JWTAuth["User"](
    retrieve_user_handler=retrieve_jwt_user_handler,
    token_secret=get_pub_key() if not settings.TESTING else PUBLIC_KEY_FOR_TESTING,
    exclude=[
        "/auth/login",
        "/auth/callback",
        "/schema",
        "/streetview/auth/mapillary/login",
        "/streetview/auth/mapillary/callback",
    ],
    auth_header="X-Tapis-Token",
    verify_expiry=True,
    algorithm="RS256",
    authentication_middleware_class=GeoAPIJWTAuthMiddleware,
    token_cls=GeoAPIToken,
)


alchemy = SQLAlchemyPlugin(config=sqlalchemy_config)
logging_middleware_config = LoggingMiddlewareConfig()
cookie_session_config = CookieBackendConfig(secret=urandom(16))  # type: ignore
openapi_config = OpenAPIConfig(
    title="GeoAPI",
    version="3.0.0",
    # components=[jwt_auth.openapi_components],
    # security=[jwt_auth.security_requirement],
    # use_handler_docstrings=True,
    # render_plugins=[ScalarRenderPlugin(version="latest")],
)

# Register exception handlers
exception_handlers = {
    InvalidGeoJSON: geojson_exception_handler,
    ApiException: api_exception_handler,
    InvalidEXIFData: exif_exception_handler,
    InvalidCoordinateReferenceSystem: coordinate_reference_system_exception_handler,
    ProjectSystemPathWatchFilesAlreadyExists: project_system_path_watch_files_already_exists_handler,
    StreetviewAuthException: streetview_auth_exception_handler,
    StreetviewLimitException: streetview_limit_exception_handler,
    AuthenticationIssue: authentication_issue_exception_handler,
}


app = Litestar(
    route_handlers=[api_router],
    middleware=[
        # TapisTokenRefreshMiddleware,
        logging_middleware_config.middleware,
        cookie_session_config.middleware,
        session_auth_config.middleware,
        jwt_auth.middleware,
    ],
    plugins=[alchemy, channels],
    on_startup=[get_db_connection],
    on_shutdown=[close_db_connection],
    stores=stores,
    exception_handlers=exception_handlers,
    csrf_config=csrf_config,
    logging_config=LoggingConfig(
        root={"level": "DEBUG", "handlers": ["console"]},
        formatters={
            "standard": {
                "format": "%(asctime)s :: %(levelname)s :: [%(filename)s:%(lineno)d] :: %(message)s"
            }
        },
        log_exceptions="always",
    ),
    on_app_init=[jwt_auth.on_app_init, session_auth.on_app_init],
    openapi_config=openapi_config,
    debug=settings.DEBUG if hasattr(settings, "DEBUG") else False,
)
