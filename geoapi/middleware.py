from __future__ import annotations

import dataclasses
import jwt
import msgspec
from typing import TYPE_CHECKING, Any, Sequence
from datetime import datetime, timezone
from litestar.exceptions import ImproperlyConfiguredException, NotAuthorizedException
from litestar.middleware import (
    AuthenticationResult,
)
from litestar.security.session_auth import SessionAuthMiddleware
from litestar.security.jwt import JWTAuthenticationMiddleware
from litestar.security.jwt.token import Token, JWTDecodeOptions
from litestar.types import Empty
from geoapi.utils.users import is_anonymous

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection
    from typing_extensions import Self


class GeoAPISessionAuthMiddleware(SessionAuthMiddleware):
    """Middleware for session authentication in GeoAPI."""

    async def authenticate_request(
        self, connection: "ASGIConnection[Any, Any, Any, Any]"
    ) -> AuthenticationResult:
        """Authenticate an incoming connection.

        Args:
            connection: An :class:`ASGIConnection <.connection.ASGIConnection>` instance.

        Raises:
            NotAuthorizedException: if session data is empty or user is not found.

        Returns:
            :class:`AuthenticationResult <.middleware.authentication.AuthenticationResult>`
        """
        if not connection.session or connection.scope["session"] is Empty:
            # the assignment of 'Empty' forces the session middleware to clear session data.
            connection.scope["session"] = Empty

        user = await self.retrieve_user_handler(connection.session, connection)

        return AuthenticationResult(user=user, auth=connection.session)


class GeoAPIJWTAuthMiddleware(JWTAuthenticationMiddleware):
    """Middleware for JWT authentication in GeoAPI."""

    async def authenticate_request(
        self, connection: "ASGIConnection[Any, Any, Any, Any]"
    ) -> AuthenticationResult:
        """Given an HTTP Connection, parse the JWT api key stored in the header and retrieve the user correlating to the
        token from the DB.

        Args:
            connection: An Litestar HTTPConnection instance.

        Returns:
            AuthenticationResult

        Raises:
            NotAuthorizedException: If token is invalid or user is not found.
        """
        if connection.user and not is_anonymous(connection.user):
            return AuthenticationResult(user=connection.user, auth=connection.session)

        auth_header = connection.headers.get(self.auth_header)
        if not auth_header:
            user = await self.retrieve_user_handler(None, connection)
            return AuthenticationResult(user=user, auth=None)

        # Accommodate both "Authorization: Bearer <token>" and plain JWT in header
        encoded_token = (
            auth_header.partition(" ")[-1] if " " in auth_header else auth_header
        )
        return await self.authenticate_token(
            encoded_token=encoded_token, connection=connection
        )


class GeoAPIToken(Token):
    """Custom Token class for GeoAPI JWT handling.

    Note: The purpose of this subclass is to override the `decode` method to
    ignore the `iat` claim during token decoding and validation, as Tapis does not
    include it in their issued tokens. This could be removed if Tapis adds the `iat` claim
    to their tokens in the future.

    removed after line 177:
        ```
            payload["iat"] = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        ```
    """

    token: str

    @classmethod
    def decode(
        cls,
        encoded_token: str,
        secret: str,
        algorithm: str,
        audience: str | Sequence[str] | None = None,
        issuer: str | Sequence[str] | None = None,
        require_claims: Sequence[str] | None = None,
        verify_exp: bool = True,
        verify_nbf: bool = True,
        strict_audience: bool = False,
    ) -> Self:
        """Decode a passed in token string and return a Token instance.

        Args:
            encoded_token: A base64 string containing an encoded JWT.
            secret: The secret with which the JWT is encoded.
            algorithm: The algorithm used to encode the JWT.
            audience: Verify the audience when decoding the token. If the audience in
                the token does not match any audience given, raise a
                :exc:`NotAuthorizedException`
            issuer: Verify the issuer when decoding the token. If the issuer in the
                token does not match any issuer given, raise a
                :exc:`NotAuthorizedException`
            require_claims: Verify that the given claims are present in the token
            verify_exp: Verify that the value of the ``exp`` (*expiration*) claim is in
                the future
            verify_nbf: Verify that the value of the ``nbf`` (*not before*) claim is in
                the past
            strict_audience: Verify that the value of the ``aud`` (*audience*) claim is
                a single value, and not a list of values, and matches ``audience``
                exactly. Requires the value passed to the ``audience`` to be a sequence
                of length 1

        Returns:
            A decoded Token instance.

        Raises:
            NotAuthorizedException: If the token is invalid.
        """

        options: JWTDecodeOptions = {
            "verify_aud": bool(audience),
            "verify_iss": bool(issuer),
        }
        if require_claims:
            options["require"] = list(require_claims)
        if verify_exp is False:
            options["verify_exp"] = False
        if verify_nbf is False:
            options["verify_nbf"] = False
        if strict_audience:
            if audience is None or (
                not isinstance(audience, str) and len(audience) != 1
            ):
                raise ValueError(
                    "When using 'strict_audience=True', 'audience' must be a sequence of length 1"
                )
            options["strict_aud"] = True
            # although not documented, pyjwt requires audience to be a string if
            # using the strict_aud option
            if not isinstance(audience, str):
                audience = audience[0]

        try:
            payload = cls.decode_payload(
                encoded_token=encoded_token,
                secret=secret,
                algorithms=[algorithm],
                audience=audience,
                issuer=list(issuer) if issuer else None,
                options=options,
            )
            # msgspec can do these conversions as well, but to keep backwards
            # compatibility, we do it ourselves, since the datetime parsing works a
            # little bit different there
            payload["exp"] = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

            # set token attribute to GeoAPIToken instance
            cls.token = encoded_token

            extra_fields = payload.keys() - {f.name for f in dataclasses.fields(cls)}
            extras = payload.setdefault("extras", {})
            for key in extra_fields:
                extras[key] = payload.pop(key)
            return msgspec.convert(payload, cls, strict=False)
        except (
            KeyError,
            jwt.exceptions.InvalidTokenError,
            ImproperlyConfiguredException,
            msgspec.ValidationError,
        ) as e:
            raise NotAuthorizedException("Invalid token") from e
