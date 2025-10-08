import requests
import secrets
from typing import TYPE_CHECKING, Any
from datetime import datetime, timedelta
from urllib.parse import urlencode
from litestar import Controller, get, Request, Response
from litestar.response import Redirect
from litestar.exceptions import HTTPException
from geoapi.services.users import UserService
from geoapi.settings import settings
from geoapi.services.streetview import StreetviewService
from geoapi.models import Streetview
from geoapi.log import logging
from geoapi.exceptions import AuthenticationIssue
from geoapi.utils.client_backend import (
    validate_referrer_url,
    get_client_url,
    get_deployed_geoapi_url,
)
from geoapi.models import User


def get_auth_state():
    return secrets.token_hex(24)


if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class StreetviewMapillaryAuthController(Controller):
    path = "/streetview/auth"

    @get(
        "/mapillary/login",
        operation_id="mapillary_login",
        description="Login via Mapillary OAuth",
    )
    async def mapillary_login(self, request: "Request[User, Any, Any]") -> Redirect:
        session = request.session
        username = request.user.username
        logger.info(
            f"Staring Mapillary's OAuth 2.0 authorization "
            f"code flow for user:{username}"
        )
        to = request.query_params.get("to", "/")

        referrer = request.headers.get("referer")
        validate_referrer_url(referrer)
        client_url = get_client_url(referrer)

        session["mapillary_auth_state"] = get_auth_state()
        session["to"] = to
        session["clientBaseUrl"] = client_url
        session["username"] = username
        session["tenant_id"] = request.user.tenant_id

        callback_url = f"{get_deployed_geoapi_url()}/streetview/auth/mapillary/callback"

        auth_params = {
            "client_id": settings.MAPILLARY_CLIENT_ID,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": settings.MAPILLARY_SCOPE,
            "state": session["mapillary_auth_state"],
        }

        auth_url = f"{settings.MAPILLARY_AUTH_URL}?{urlencode(auth_params)}"

        # Redirect user to Mapillary authorization page
        return Redirect(auth_url)

    @get(
        "/mapillary/callback",
        operation_id="mapillary_callback",
        description="Handle Mapillary OAuth callback",
    )
    async def mapillary_callback(
        self,
        request: "Request[User, Any, Any]",
        db_session: "Session",
    ) -> Redirect:
        session = request.session
        logger.info(
            f"Handling callback from Mapillary's OAuth 2.0 authorization "
            f"code flow for user:{session.get('username')}"
        )

        auth_state = session.pop("mapillary_auth_state")
        if auth_state != request.query_params.get("state"):
            logger.error("State not matching")
            raise AuthenticationIssue("State not matching")

        client_base_url = session.pop("clientBaseUrl")
        client_redirect_uri = f"{client_base_url}{session['to']}"

        code = request.query_params.get("code")
        error = request.query_params.get("error")
        if error or not code:
            if error:
                logger.error(f"Error: {error}. Redirecting back to client")
            else:
                logger.error("No authorization code received")
            return Redirect(client_redirect_uri)

        callback_url = f"{get_deployed_geoapi_url()}/streetview/auth/mapillary/callback"

        token_data = {
            "grant_type": "AUTHORIZATION_CODE",
            "code": code,
            "client_id": settings.MAPILLARY_CLIENT_ID,
            "redirect_uri": callback_url,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"OAuth {settings.MAPILLARY_CLIENT_SECRET}",
        }

        # Make token exchange request
        token_request_timestamp = datetime.now(datetime.timezone.utc)
        response = requests.post(
            settings.MAPILLARY_API_URL + "/token", headers=headers, json=token_data
        )

        if response.status_code != 200:
            logger.error(f"Failed to obtain access token. details: {response.text}")
            raise HTTPException(status_code=400, detail="Failed to obtain access token")

        # Extract token information
        token_info = response.json()
        access_token = token_info.get("access_token")
        expires_in = token_info.get(
            "expires_in"
        )  # Expiry duration in seconds (2 months for mapillary)
        token_expires_at = token_request_timestamp + timedelta(seconds=expires_in)

        username = session.get("username")
        tenant_id = session.get("tenant_id")
        if not username or not tenant_id:
            logger.error("Username or tenant_id not found in session")
            raise HTTPException(status_code=400, detail="Invalid session state")
        user = UserService.getUser(db_session, username, tenant_id)

        logger.info(f"Updating mapillary information for user {username}")

        user_mapillary = StreetviewService.getByService(
            db_session, user, service="mapillary"
        )
        if not user_mapillary:
            user_mapillary = Streetview(user_id=user.id, service="mapillary")
            user_mapillary.user_id = user.id
            user_mapillary.service = "mapillary"

        user_mapillary.token = access_token
        user_mapillary.token_expires_at = token_expires_at
        db_session.add(user_mapillary)
        db_session.commit()

        # Redirect back to the client application
        return Redirect(client_redirect_uri)

    @get(
        "/mapillary/",
        operation_id="mapillary_auth_delete",
        description="Delete Mapillary OAuth authentication",
    )
    async def mapillary_auth_delete(
        self, request: "Request[User, Any, Any]", db_session: "Session"
    ) -> Response:
        """
        Delete Mapillary OAuth authentication for the current user.
        """
        user = request.user
        StreetviewService.deleteAuthByService(db_session, user, service="mapillary")

        return Response(status_code=204)
