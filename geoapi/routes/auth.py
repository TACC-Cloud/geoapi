from flask import redirect, request, session, abort, session
from flask_restx import Resource, Namespace
import requests
import secrets
import urllib

from geoapi.settings import settings
from geoapi.log import logging
from geoapi.db import db_session
from geoapi.utils import jwt_utils
from geoapi.services.users import UserService, ExpiredTokenError
from geoapi.utils.tenants import get_tapis_api_server
from geoapi.exceptions import AuthenticationIssue, ApiException
from geoapi.utils.decorators import valid_user_session


logger = logging.getLogger(__name__)

api = Namespace("auth")


def get_auth_state():
    return secrets.token_hex(24)


def validate_referrer_url(referrer_url):
    """Check if referrer url is valid.  Raises AuthenticationIssue if not valid."""
    client_url_from_request_url = get_client_url(referrer_url)
    if client_url_from_request_url is None:
        logger.exception(f"Issue with referrer url: {referrer_url}")
        raise AuthenticationIssue(
            "Authentication error: Requesting client not expected"
        )


def get_client_url(url):
    """
    Get requesting client URLs.

    This function checks if the provided URL starts with any of the predefined client URLs. If a match is found,
    it returns the matching client URL. If no match is found, it returns None
    """
    client_urls = [
        "http://localhost:4200/",
        "http://hazmapper.local:4200/",
        "https://hazmapper.tacc.utexas.edu/hazmapper/",
        "https://hazmapper.tacc.utexas.edu/staging/",
        "https://hazmapper.tacc.utexas.edu/dev/",
        "https://hazmapper.tacc.utexas.edu/exp/",
        "https://hazmapper.tacc.utexas.edu/hazmapper-react/",
        "https://hazmapper.tacc.utexas.edu/staging-react/",
        "https://hazmapper.tacc.utexas.edu/dev-react/",
        "https://hazmapper.tacc.utexas.edu/exp-react/",
        "https://hazmapper.tacc.utexas.edu/taggit/",
        "https://hazmapper.tacc.utexas.edu/taggit-staging/",
        "https://hazmapper.tacc.utexas.edu/taggit-dev/",
        "https://hazmapper.tacc.utexas.edu/taggit-exp/",
    ]
    for client in client_urls:
        if url.startswith(client):
            return client.rstrip("/")
    return None


def get_deployed_geoapi_url():
    """
    Get backend url

    This function checks if the provided URL starts with any of the predefined backend URLs. If a match is found,
    it returns the matching client URL. If no match is found, raises API
    """
    geoapi_urls = {
        "local": "http://localhost:8888",
        "production": "https://hazmapper.tacc.utexas.edu/geoapi",
        "staging": "https://hazmapper.tacc.utexas.edu/geoapi-staging",
        "dev": "https://hazmapper.tacc.utexas.edu/geoapi-dev",
        "experimental": "https://hazmapper.tacc.utexas.edu/geoapi-experimental",
        "testing": "http://test:8888",
    }
    if settings.APP_ENV in geoapi_urls:
        return geoapi_urls[settings.APP_ENV]
    else:
        logger.exception(f"Unknown/unsupported APP_ENV:{settings.APP_ENV}")
        raise ApiException(f"Unknown APP_ENV:{settings.APP_ENV}")


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
            access_token_expires_at = response_json["access_token"]["expires_at"] # note: not using "expires_in"
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

            # Store user information in session
            session['username'] = username
            session['tenant'] = tenant

            encoded_params = urllib.parse.urlencode({"to": to})
            client_redirect_uri = f"{client_base_url}/handle-login?{encoded_params}"
            return redirect(client_redirect_uri)


@api.route("/csrf-token")
class CSRFToken(Resource):
    @api.doc(id="get-csrf-token", description="Get CSRF token for the current session")
    @valid_user_session
    def get(self):
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)

        return {
            "csrf_token": session['csrf_token']
        }


@api.route("/tapis/token")
class GetTapisToken(Resource):
    @api.doc(id="get-tapis-token", description="Retrieve Tapis token for the authenticated user")
    @valid_user_session
    def get(self):
        u = request.current_user
        try:
            UserService.check_and_refresh_access_token(database_session=db_session, user=u)

            return {
                "token": u.auth.access_token,
                "username": session['username'],
                "tenant": session['tenant']
            }
        except ExpiredTokenError as e:
            # should not happen as our session should expire before refresh token expires
            logger.exception(f"Unexpected token issue: {e}")
            session.clear()
            abort(401, "Invalid or expired token")


@api.route("/logout")
class Logout(Resource):
    def get(self):
        client_base_url = session.pop("clientBaseUrl")

        # Clear the sessions
        session.clear()

        # Create response that clears the token cookie
        return redirect(client_base_url + "logout")
