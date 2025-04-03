from flask import redirect, request, session
from flask_restx import Resource, Namespace
import requests
import secrets
import urllib

from geoapi.settings import settings
from geoapi.log import logging
from geoapi.db import db_session
from geoapi.utils import jwt_utils
from geoapi.services.users import UserService
from geoapi.utils.tenants import get_tapis_api_server
from geoapi.utils.client_backend import (
    validate_referrer_url,
    get_client_url,
    get_deployed_geoapi_url,
)
from geoapi.exceptions import AuthenticationIssue, ApiException


logger = logging.getLogger(__name__)

api = Namespace("auth")


def get_auth_state():
    return secrets.token_hex(24)


@api.route("/login")
class Login(Resource):
    @api.doc(id="login", description="Login via oauth")
    def get(self):
        to = request.args.get("to", "/")

        validate_referrer_url(request.referrer)
        client_url = get_client_url(request.referrer)

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
            "user is starting login process; " "user is being redirected to tapis"
        )
        return redirect(authorization_url)


@api.route("/callback")
class Callback(Resource):
    @api.doc(id="callback", description="Callback for oauth")
    def get(self):
        auth_state = session.pop("auth_state")
        if auth_state != request.args.get("state"):
            logger.error("State not matching")
            raise AuthenticationIssue("State not matching")

        client_base_url = session.pop("clientBaseUrl")

        error = request.args.get("error")
        if error:
            logger.error(f"Error: {error}. Redirecting to client logout")
            return redirect(client_base_url + "logout")

        code = request.args.get("code")
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

            user = UserService.getUser(db_session, username, tenant)
            if not user:
                user = UserService.create(db_session, username=username, tenant=tenant)

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

            params = {
                "access_token": access_token,
                "expires_in": access_token_expires_in,
                "expires_at": access_token_expires_at,
                "to": to,
            }
            encoded_params = urllib.parse.urlencode(params)
            client_redirect_uri = f"{client_base_url}/handle-login#{encoded_params}"
            return redirect(client_redirect_uri)
