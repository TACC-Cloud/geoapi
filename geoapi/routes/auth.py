import requests
import secrets
from typing import TYPE_CHECKING, Any
from litestar import Controller, get, Request, Response
from litestar.response import Redirect
from litestar.status_codes import HTTP_302_FOUND
from geoapi.settings import settings
from geoapi.log import logging
from geoapi.utils import jwt_utils
from geoapi.services.users import UserService
from geoapi.utils.tenants import get_tapis_api_server
from geoapi.utils.client_backend import (
    validate_referrer_url,
    get_client_url,
    get_deployed_geoapi_url,
)
from geoapi.exceptions import AuthenticationIssue, ApiException
from geoapi.models import User
from geoapi.utils.users import is_anonymous
from geoapi.utils.external_apis import TapisUtils

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


def get_auth_state():
    return secrets.token_hex(24)


def get_adjusted_geoapi_url(request: Request):
    # workaround while we test hazmapper.tmp
    # TODO https://tacc-main.atlassian.net/browse/WG-513 remove this method and its uses
    base_url = get_deployed_geoapi_url()

    if "hazmapper-tmp" in request.url.hostname:
        return base_url.replace("hazmapper", "hazmapper-tmp")

    return base_url


def get_client_id_key(request: Request):
    logger.info(f"Getting client id/key for host:{request.url.hostname}")
    if "hazmapper-tmp" in request.url.hostname:
        return settings.TMP_TAPIS_CLIENT_ID, settings.TMP_TAPIS_CLIENT_KEY
    return settings.TAPIS_CLIENT_ID, settings.TAPIS_CLIENT_KEY


class AuthController(Controller):
    path = "/auth"

    @get(path="/login", operation_id="login", description="Login via oauth")
    async def login(self, request: Request) -> Redirect:
        to = request.query_params.get("to", "/")
        referrer = request.headers.get("referer")
        validate_referrer_url(referrer)
        client_url = get_client_url(referrer)
        session = request.session
        session["auth_state"] = get_auth_state()
        session["to"] = to
        session["clientBaseUrl"] = client_url

        # Assuming always DesignSafe tenant if using this route
        tenant_id = "DESIGNSAFE" if not settings.TESTING else "TEST"
        tapis_server = get_tapis_api_server(tenant_id)
        # TODO use get_deployed_geoapi_url instead below;
        #  see  https://tacc-main.atlassian.net/browse/WG-51
        callback_host = get_adjusted_geoapi_url(request)
        callback_url = f"{callback_host}/auth/callback"

        # TODO Remove see https://tacc-main.atlassian.net/browse/WG-513
        client_id, client_key = get_client_id_key(request)

        authorization_url = (
            f"{tapis_server}/v3/oauth2/authorize?"
            f"client_id={client_id}&"
            f"redirect_uri={callback_url}&"
            "response_type=code&"
            f"state={session['auth_state']}"
        )
        logger.info(
            f"Starting login process; user is being redirected to tapis (referrer: {referrer})"
        )
        return Redirect(authorization_url, status_code=HTTP_302_FOUND)

    @get(operation_id="logout", path="/logout")
    async def logout(self, request: Request[User, Any, Any]) -> Redirect:
        """Account Logout"""
        logger.info(
            f"user {request.user} is logging out; clearing session and revoking token"
        )
        tapis_server = get_tapis_api_server(
            "DESIGNSAFE" if not settings.TESTING else "TEST"
        )
        referrer = request.headers.get("referer")
        validate_referrer_url(referrer)
        client_url = get_client_url(referrer)

        if request.session:
            request.clear_session()

        logout_endpoint = (
            f"{tapis_server}/v3/oauth2/logout?redirect_url={client_url}/logged-out"
        )

        return Redirect(logout_endpoint)

    @get(path="/callback", id="callback", description="Callback for oauth login")
    async def callback(self, request: Request, db_session: "Session") -> Redirect:
        session = request.session
        auth_state = session.pop("auth_state", None)
        if not auth_state or auth_state != request.query_params.get("state"):
            logger.error("State not matching")
            raise AuthenticationIssue("State not matching")
        client_base_url = session.pop("clientBaseUrl", None)
        error = request.query_params.get("error")
        if error:
            logger.error(f"Error: {error}. Redirecting to client logout")
            return Redirect(client_base_url + "logout", status_code=HTTP_302_FOUND)
        code = request.query_params.get("code")
        if code:
            to = session.pop("to", "/")
            tapis_server = get_tapis_api_server(
                "DESIGNSAFE" if not settings.TESTING else "TEST"
            )
            # TODO use get_deployed_geoapi_url instead below;
            #  see  https://tacc-main.atlassian.net/browse/WG-51
            callback_host = get_adjusted_geoapi_url(request)
            callback_url = f"{callback_host}/auth/callback"

            # TODO Remove see https://tacc-main.atlassian.net/browse/WG-513
            client_id, client_key = get_client_id_key(request)
            logger.info(f"Using client_id ({client_id}) and key for auth flow")

            body = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": callback_url,
            }
            # t = Tapis(
            #     base_url=tapis_server,
            #     client_id=settings.TAPIS_CLIENT_ID,
            #     client_key=settings.TAPIS_CLIENT_KEY)
            # response = t.authenticator.create_token(
            #     grant_type="authorization_code",
            #     code=code,
            #     redirect_uri=callback_url,)
            response = requests.post(
                f"{tapis_server}/v3/oauth2/tokens",
                data=body,
                auth=(client_id, client_key),
            )
            if not response.ok:
                logger.error(
                    f"Token request failed: {response.status_code} - {response.text}"
                )
                raise AuthenticationIssue("OAuth token exchange failed")

            response_json = response.json()["result"]

            access_token = response_json["access_token"]["access_token"]
            access_token_expires_at = response_json["access_token"]["expires_at"]
            refresh_token = response_json["refresh_token"]["refresh_token"]
            refresh_token_expires_at = response_json["refresh_token"]["expires_at"]

            try:
                decoded = jwt_utils.decode_token(
                    access_token, verify=not settings.TESTING
                )
                username = decoded["tapis/username"]
                tenant = decoded["tapis/tenant_id"]
            except Exception as e:
                logger.exception(f"There is an issue decoding the JWT: {e}")
                raise ApiException("There is an issue decoding the JWT in the callback")

            user = UserService.getOrCreateUser(
                database_session=db_session, username=username, tenant=tenant
            )
            UserService.update_tokens(
                db_session,
                user,
                access_token,
                access_token_expires_at,
                refresh_token,
                refresh_token_expires_at,
            )

            # commit changes before redirect in case there was an error
            db_session.commit()

            # Build response with redirect
            response = Redirect(f"{client_base_url}{to}", status_code=HTTP_302_FOUND)

            request.set_session({"username": username, "tenant": tenant})
            return response

    @get(
        path="/user",
        operation_id="get_user_info",
        description="Get user information",
    )
    async def get_user_info(
        self,
        request: Request[User, Any, Any],
        db_session: "Session",
    ) -> Response:
        """Get user information"""
        if is_anonymous(request.user):
            return Response({"username": None, "authToken": None}, status_code=200)

        tapis = TapisUtils(db_session, request.user)
        tapis._ensure_valid_token(buffer=60 * 30)  # 30 minutes buffer
        user_info = {
            "username": tapis.user.username,
            "authToken": {
                "token": tapis.user.jwt,
                "expiresAt": tapis.user.auth.access_token_expires_at,
            },
        }

        return Response(user_info, status_code=200)
