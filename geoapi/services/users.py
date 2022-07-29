from geoapi.models import User, Project, ProjectUser
from geoapi.db import db_session


class UserService:

    @staticmethod
    def create(username: str, tenant: str, jwt: str = None) -> User:
        """

        :rtype: User
        """
        u = User(username=username, tenant_id=tenant)
        if jwt:
            u.jwt = jwt
        db_session.add(u)
        db_session.commit()
        return u

    @staticmethod
    def checkUser(username: str) -> bool:
        # TODO: Add in TAS check
        pass

    @staticmethod
    def getOrCreateUser(username: str, tenant: str) -> User:
        user = UserService.getUser(username, tenant)
        if not user:
            user = UserService.create(username, tenant)
        return user

    @staticmethod
    def getUser(username: str, tenant: str) -> User:
        return db_session.query(User)\
            .filter(User.username == username)\
            .filter(User.tenant_id == tenant)\
            .first()

    @staticmethod
    def get(userId: int) -> User:
        return db_session.query(User).get(userId)

    @staticmethod
    def canAccess(user: User, projectId: int) -> bool:
        up = db_session.query(ProjectUser)\
            .join(Project)\
            .filter(ProjectUser.user_id == user.id)\
            .filter(Project.tenant_id == user.tenant_id)\
            .filter(ProjectUser.project_id == projectId).first()
        if up:
            return True
        return False

    @staticmethod
    def is_admin_or_creator(user: User, projectId: int) -> bool:
        up = db_session.query(ProjectUser) \
            .join(Project) \
            .filter(ProjectUser.user_id == user.id) \
            .filter(Project.tenant_id == user.tenant_id) \
            .filter(ProjectUser.project_id == projectId).first()
        if up:
            return up.admin or up.creator
        return False

    @staticmethod
    def setJWT(user: User, token: str) -> None:
        user.jwt = token
        db_session.commit()

    @staticmethod
    def setMapillaryToken(user: User, token: str) -> None:
        user.google_jwt = token
        db_session.commit()

    @staticmethod
    def setGoogleToken(user: User, token: str) -> None:
        user.mapillary_jwt = token
        db_session.commit()
