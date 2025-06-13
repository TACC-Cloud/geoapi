"""GeoAPI Application Module"""

import logging
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
from litestar.security.session_auth import SessionAuth
from litestar.stores.redis import RedisStore
from litestar.stores.registry import StoreRegistry
from litestar.exceptions import InternalServerException
from litestar.connection import ASGIConnection
from litestar.security.jwt import JWTAuth, Token
from litestar.plugins.sqlalchemy import (
    SyncSessionConfig,
    SQLAlchemySyncConfig,
    SQLAlchemyPlugin,
)
from geoapi.routes import api_router
from geoapi.settings import settings
from geoapi.db import get_db_connection, close_db_connection, get_db_connection_string
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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from geoapi.models import User

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)


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


csrf_config = CSRFConfig(
    secret="my-secret", cookie_name="some-cookie-name", header_name="some-header-name"
)

logging_middleware_config = LoggingMiddlewareConfig()

cookie_session_config = CookieBackendConfig(secret=urandom(16))  # type: ignore

root_store = RedisStore.with_client(url="redis://geoapi_redis:6379/0")

# We add the session security schema to the OpenAPI config.
openapi_config = OpenAPIConfig(
    title="GeoAPI",
    version="3.0.0",
    # components=[jwt_auth.openapi_components],
    # security=[jwt_auth.security_requirement],
    # use_handler_docstrings=True,
    # render_plugins=[ScalarRenderPlugin(version="latest")],
)


async def retrieve_jwt_user_handler(
    token: Token,
    connection: ASGIConnection[Any, Any, Any, Any],
    db_session: "Session",
) -> "User":
    """Used by the JWTAuth Middleware to retrieve the user from the JWT token."""
    # logic here to retrieve the user instance
    user = None

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
            #   (It is more common that user will be using an auth flow were hazmapper will auth
            #   with geoapi to get the token. BUT we can't assume that as it is also possible that
            #   user just uses geoapi as a service with token generated somewhere else. So we need
            #   to get/update just their access token for these cases)
            UserService.update_access_token(db_session, user, token)
    return user


jwt_auth = JWTAuth["User"](
    retrieve_user_handler=retrieve_jwt_user_handler,
    token_secret=get_pub_key() if not settings.TESTING else PUBLIC_KEY_FOR_TESTING,
    # This is a regex that matches any path that does not start with /status, /projects, or /notifications.
    exclude=[
        r"^(?!\/(status|projects|notifications|streetview|streetview_auth/mapillary/prepare|streetview_auth/mapillary/)(\/.*)?$).*$"
    ],
    auth_header="X-Tapis-Token",
    verify_expiry=True,
    algorithm="RS256",
)


async def retrieve_session_user_handler(
    session: dict[str, Any],
    connection: ASGIConnection[Any, Any, Any, Any],
) -> "User":
    """Used by the SessionAuth Middleware to retrieve the user from the session."""
    username = session.get("username")
    tenant = session.get("tenant")
    db_session = connection.scope.get("db_session")
    if not username or not tenant:
        guest_uuid = connection.headers.get("X-Guest-UUID")
        return AnonymousUser(guest_unique_id=guest_uuid)
    return UserService.getUser(
        database_session=db_session, username=username, tenant=tenant
    )


session_auth = SessionAuth["User", ServerSideSessionBackend](
    retrieve_user_handler=retrieve_session_user_handler,
    # we must pass a config for a session backend.
    # all session backends are supported
    session_backend_config=ServerSideSessionConfig(),
    # exclude any URLs that should not have authentication.
    # We exclude the documentation URLs, signup and login.
    exclude=["/auth/login", "/schema"],
)

db_session_config = SyncSessionConfig(expire_on_commit=False, autoflush=False)
sqlalchemy_config = SQLAlchemySyncConfig(
    connection_string=get_db_connection_string(settings),
    session_config=db_session_config,
)


# Create Litestar app
app = Litestar(
    route_handlers=[api_router],
    middleware=[
        # TapisTokenRefreshMiddleware,
        logging_middleware_config.middleware,
        cookie_session_config.middleware,
        ServerSideSessionConfig().middleware,
        session_auth.middleware,
    ],
    plugins=[SQLAlchemyPlugin(config=sqlalchemy_config)],
    on_startup=[get_db_connection],
    on_shutdown=[close_db_connection],
    stores=StoreRegistry(default_factory=root_store.with_namespace),
    exception_handlers=exception_handlers,
    csrf_config=csrf_config,
    logging_config=LoggingConfig(
        root={"level": "DEBUG", "handlers": ["console"]},
        formatters={
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        },
        log_exceptions="always",
    ),
    on_app_init=[
        session_auth.on_app_init,
        # jwt_auth.on_app_init
    ],
    openapi_config=openapi_config,
    debug=settings.DEBUG if hasattr(settings, "DEBUG") else False,
)
