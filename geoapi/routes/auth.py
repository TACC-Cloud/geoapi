import requests
import secrets
import urllib
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
from tapipy.tapis import Tapis
from tapipy.errors import BaseTapyException
from geoapi.models import User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


def get_auth_state():
    return secrets.token_hex(24)


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
        callback_url = f"{get_deployed_geoapi_url()}/auth/callback"

        authorization_url = (
            f"{tapis_server}/v3/oauth2/authorize?"
            f"client_id={settings.TAPIS_CLIENT_ID}&"
            f"redirect_uri={callback_url}&"
            "response_type=code&"
            f"state={session['auth_state']}"
        )
        logger.info(
            f"Starting login process; user is being redirected to tapis (referrer: {referrer})"
        )
        return Redirect(authorization_url, status_code=HTTP_302_FOUND)

    @get(operation_id="logout", path="/logout", exclude_from_auth=True)
    async def logout(self, request: Request[User, Any, Any]) -> Response:
        """Account Logout"""
        logger.info(
            f"user {request.user} is logging out; clearing session and revoking token"
        )
        tapis_server = get_tapis_api_server(
            "DESIGNSAFE" if not settings.TESTING else "TEST"
        )
        user = request.user

        try:
            client = Tapis(base_url=tapis_server, access_token=user.access_token)
            response = client.authenticator.revoke_token(token=user.access_token)
            logger.info("revoke response is %s" % response)
        except BaseTapyException as e:
            logger.error("Error revoking token: %s", e.message)

        if request.session:
            request.clear_session()

        return Response(
            {"message": "OK"},
            status_code=200,
        )

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
            callback_url = f"{get_deployed_geoapi_url()}/auth/callback"
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
                auth=(settings.TAPIS_CLIENT_ID, settings.TAPIS_CLIENT_KEY),
            )
            response_json = response.json()["result"]

            access_token = response_json["access_token"]["access_token"]
            access_token_expires_in = response_json["access_token"]["expires_in"]
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

            # This can be removed once we have proper session management not dependent on the client-side handling session state
            params = {
                "access_token": access_token,
                "expires_in": access_token_expires_in,
                "expires_at": access_token_expires_at,
                "to": to,
            }
            encoded_params = urllib.parse.urlencode(params)
            client_redirect_uri = f"{client_base_url}/handle-login#{encoded_params}"

            # Build response with redirect
            response = Redirect(client_redirect_uri, status_code=HTTP_302_FOUND)

            request.set_session({"username": username, "tenant": tenant})
            return response
