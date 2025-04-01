import requests
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from geoapi.services.users import UserService
from geoapi.settings import settings
from geoapi.services.streetview import StreetviewService
from geoapi.models import Streetview
from geoapi.log import logging
from geoapi.utils.decorators import jwt_decoder
from geoapi.db import db_session
from geoapi.exceptions import AuthenticationIssue
from geoapi.utils.client_backend import (
    validate_referrer_url,
    get_client_url,
    get_deployed_geoapi_url,
)
from flask_restx import Namespace, Resource
from flask import request, redirect, session, jsonify, abort
import jwt


def get_auth_state():
    return secrets.token_hex(24)


logger = logging.getLogger(__name__)

api = Namespace("streetview_auth", path="/streetview/auth")


# TODO: this is a work around for lack of sessions
#  endpoint can be removed once sessions are completed. See WG-472
@api.route("/mapillary/prepare")
class MapillaryLoginPrepare(Resource):
    @jwt_decoder
    def post(self):
        payload = {
            "username": request.current_user.username,
            "tenant": request.current_user.tenant_id,
            "exp": datetime.utcnow() + timedelta(minutes=5),
        }
        temp_token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        return jsonify({"tempToken": temp_token})


# Route for initiating Mapillary login
@api.route("/mapillary/login")
class MapillaryLogin(Resource):
    def get(self):
        # TODO Using temp token as query parameter; this can be removed once auth sessions
        #  are used and then we can just use request.current_user. See WG-472
        temp_token = request.args.get("temp_token")
        try:
            # Decode and verify the JWT
            payload = jwt.decode(temp_token, settings.SECRET_KEY, algorithms=["HS256"])
            username = payload["username"]
            tenant = payload["tenant"]
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return redirect("/auth-error?reason=expired_token")

        logger.info(
            f"Staring Mapillary's OAuth 2.0 authorization "
            f"code flow for user:{username}"
        )
        to = request.args.get("to", "/")

        validate_referrer_url(request.referrer)
        client_url = get_client_url(request.referrer)

        session["mapillary_auth_state"] = get_auth_state()
        session["to"] = to
        session["clientBaseUrl"] = client_url
        session["username"] = username
        session["tenant_id"] = tenant

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
        return redirect(auth_url)


# Route for handling Mapillary callback
@api.route("/mapillary/callback")
class MapillaryCallback(Resource):
    def get(self):
        logger.info(
            f"Handling callback from Mapillary's OAuth 2.0 authorization "
            f"code flow for user:{session.get('username')}"
        )

        auth_state = session.pop("mapillary_auth_state")
        if auth_state != request.args.get("state"):
            logger.error("State not matching")
            raise AuthenticationIssue("State not matching")

        client_base_url = session.pop("clientBaseUrl")
        client_redirect_uri = f"{client_base_url}{session['to']}"

        code = request.args.get("code")
        error = request.args.get("error")
        if error or not code:
            if error:
                logger.error(f"Error: {error}. Redirecting back to client")
            else:
                logger.error("No authorization code received")
            return redirect(client_redirect_uri)

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
        token_request_timestamp = datetime.utcnow()
        response = requests.post(
            settings.MAPILLARY_API_URL + "/token", headers=headers, json=token_data
        )

        if response.status_code != 200:
            logger.error(f"Failed to obtain access token. details: {response.text}")
            abort(400, "Failed to obtain access token")

        # Extract token information
        token_info = response.json()
        access_token = token_info.get("access_token")
        expires_in = token_info.get(
            "expires_in"
        )  # Expiry duration in seconds (2 months for mapillary)
        token_expires_at = token_request_timestamp + timedelta(seconds=expires_in)

        username = session.get("username")
        tenant_id = session.get("tenant_id")
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
        return redirect(client_redirect_uri)


@api.route("/mapillary/")
class MapillaryAuthDelete(Resource):
    @jwt_decoder
    def delete(self):
        u = request.current_user
        return StreetviewService.deleteAuthByService(db_session, u, service="mapillary")
