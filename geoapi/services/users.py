from datetime import datetime, timedelta, timezone
import requests
from sqlalchemy.exc import InvalidRequestError

from geoapi.models import Auth, User, Project, ProjectUser
from geoapi.utils import jwt_utils
from geoapi.utils.tenants import get_tapis_api_server
from geoapi.log import logger


class ExpiredTokenError(Exception):
    """Token is expired"""

    pass


class RefreshTokenError(Exception):
    """Issue during refresh token"""

    pass


class RefreshTokenExpired(Exception):
    """Refresh token has expired"""

    pass


class UserService:

    @staticmethod
    def create(
        database_session, username: str, tenant: str, access_token: str = None
    ) -> User:
        """
        Create a new user with an optional access token.
        """
        user = User(username=username, tenant_id=tenant)
        database_session.add(user)
        database_session.commit()

        # Create the associated Auth record
        auth = Auth(user_id=user.id)
        if access_token:
            auth.access_token = access_token
        database_session.add(auth)
        database_session.commit()

        # Refresh the user to include the newly created auth relationship
        database_session.refresh(user)

        return user

    @staticmethod
    def getOrCreateUser(database_session, username: str, tenant: str) -> User:
        user = UserService.getUser(database_session, username, tenant)
        if not user:
            user = UserService.create(database_session, username, tenant)
        return user

    @staticmethod
    def getUser(database_session, username: str, tenant: str) -> User:
        user = (
            database_session.query(User)
            .filter(User.username == username)
            .filter(User.tenant_id == tenant)
            .first()
        )

        # Need to ensure now that old users have an auth entry
        if user and user.auth is None:
            auth = Auth(user_id=user.id)
            database_session.add(auth)
            database_session.commit()
            database_session.refresh(user)
        return user

    @staticmethod
    def get(database_session, userId: int) -> User:
        return database_session.get(User, userId)

    @staticmethod
    def canAccess(database_session, user: User, projectId: int) -> bool:
        up = (
            database_session.query(ProjectUser)
            .join(Project)
            .filter(ProjectUser.user_id == user.id)
            .filter(Project.tenant_id == user.tenant_id)
            .filter(ProjectUser.project_id == projectId)
            .one_or_none()
        )
        if up:
            return True
        return False

    @staticmethod
    def is_admin_or_creator(database_session, user: User, projectId: int) -> bool:
        up = (
            database_session.query(ProjectUser)
            .join(Project)
            .filter(ProjectUser.user_id == user.id)
            .filter(Project.tenant_id == user.tenant_id)
            .filter(ProjectUser.project_id == projectId)
            .one_or_none()
        )
        if up:
            return up.admin or up.creator
        return False

    @staticmethod
    def update_access_token(database_session, user: User, access_token: str) -> None:
        """
        Update the user's access token (jwt) if there is NO refresh_token

        But, we should only set it if the new token expires AFTER the current token as
        we wouldn't be improving things by using older token.

        Note: we would have NO refresh_token if we weren't using the auth flow in geoapi. This implies
        that users are getting their jwt from somewhere else.
        """
        if user.has_unexpired_refresh_token():
            # user has a refresh token so no need to update the access_token
            # as we have a valid refresh token and can use that
            return

        # if missing access token or the new one expires later, then we can update it
        if not user.auth.access_token or jwt_utils.compare_token_expiry(
            access_token, user.auth.access_token
        ):
            user.auth.access_token = access_token
            database_session.commit()

    @staticmethod
    def update_tokens(
        database_session,
        user: User,
        access_token: str,
        access_token_expires_at: int,
        refresh_token: str,
        refresh_token_expires_at: int,
    ) -> None:
        """
        Update the user's access token and refresh token
        """
        user.auth.access_token = access_token
        user.auth.access_token_expires_at = access_token_expires_at
        user.auth.refresh_token = refresh_token
        user.auth.refresh_token_expires_at = refresh_token_expires_at
        database_session.commit()

    @staticmethod
    def refresh_access_token(database_session, user: User):
        """
        Refresh user's access token using the refresh token.

        Raises:
            RefreshTokenExpired: If the refresh token is expired.
            RefreshTokenError: If there is a problem refreshing the token.
        """
        if not user.has_unexpired_refresh_token():
            logger.error(
                f"Unable to refresh token for user:{user.username} tenant:{user.tenant_id}"
                f" as refresh token is expired (or possibly never existed)"
            )
            raise RefreshTokenExpired

        try:
            logger.info(
                f"Refreshing token for user:{user.username}" f" tenant:{user.tenant_id}"
            )
            with database_session.begin_nested():
                # Acquire lock by selecting the auth row for update
                # to ensure that only one process is refreshing the tokens at a time
                locked_auth = (
                    database_session.query(Auth)
                    .filter(Auth.user_id == user.id)
                    .with_for_update()
                    .one()
                )
                logger.info(
                    f"Acquired auth for refreshing token for user:{user.username}"
                    f" tenant:{user.tenant_id}"
                )

                # Check if the tokens were updated while we were getting the `locked_auth`
                if locked_auth.access_token_expires_at:
                    current_time = datetime.now(timezone.utc)
                    buffer_time = timedelta(
                        seconds=jwt_utils.BUFFER_TIME_WHEN_CHECKING_IF_ACCESS_TOKEN_WAS_RECENTLY_REFRESHED
                    )
                    if (
                        locked_auth.access_token_expires_at - current_time
                    ) > buffer_time:
                        logger.info(
                            f"No need to refresh token for user:{user.username}"
                            f" tenant:{user.tenant_id} as it was recently refreshed"
                        )
                        return

                # Check if the tokens were updated while we were getting the `locked_auth`
                if locked_auth.access_token_expires_at:
                    current_time = datetime.utcnow().replace(tzinfo=None)
                    # Make sure `locked_auth.access_token_expires_at` is naive datetime
                    access_token_expires_at = (
                        locked_auth.access_token_expires_at.replace(tzinfo=None)
                    )
                    buffer_time = timedelta(
                        seconds=jwt_utils.BUFFER_TIME_WHEN_CHECKING_IF_ACCESS_TOKEN_WAS_RECENTLY_REFRESHED
                    )
                    if (access_token_expires_at - current_time) > buffer_time:
                        logger.info(
                            f"No need to refresh token for user:{user.username}"
                            f" tenant:{user.tenant_id} as it was recently refreshed"
                        )
                        return

                tapis_server = get_tapis_api_server(user.tenant_id)
                body = {
                    "refresh_token": locked_auth.refresh_token,
                }
                response = requests.put(f"{tapis_server}/v3/tokens", json=body)

                # TODO_TAPISV3: https://tapis-project.github.io/live-docs/?service=Tokens#tag/Tokens/operation/refresh_token
                # says return code is 201 but seeing 200
                if response.status_code == 200 or response.status_code == 201:
                    data = response.json()["result"]
                    locked_auth.access_token = data["access_token"]["access_token"]
                    locked_auth.access_token_expires_at = data["access_token"][
                        "expires_at"
                    ]
                    locked_auth.refresh_token = data["refresh_token"]["refresh_token"]
                    locked_auth.refresh_token_expires_at = data["refresh_token"][
                        "expires_at"
                    ]
                    database_session.commit()
                    logger.info(
                        f"Finished refreshing token for user:{user.username}"
                        f" tenant:{user.tenant_id}"
                    )
                else:
                    logger.error(
                        f"Problem refreshing token for user:{user.username}"
                        f" tenant:{user.tenant_id}: {response}, {response.text}"
                    )
                    raise RefreshTokenError
            # Re-query the updated user after the transaction is committed
            # (so that the caller has the latest state which includes the updated auth token)
            database_session.refresh(user)
        except InvalidRequestError as ire:
            logger.exception(
                f"Transaction error during token refresh for user:{user.username}: {str(ire)}"
            )
            raise RefreshTokenError from ire
        except Exception as e:
            database_session.rollback()
            logger.exception(
                f"Error during token refresh for user:{user.username}: {str(e)}"
            )
            raise RefreshTokenError from e
