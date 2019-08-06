from geoapi.models import User, Project, ProjectUser
from geoapi.db import db_session
from typing import List
# from pytas.http import TASClient

class UserService:

    @staticmethod
    def create(username: str, jwt: str, tenant: str) -> User:
        """

        :rtype: User
        """
        u = User(username=username, jwt=jwt, tenant_id=tenant)
        db_session.add(u)
        db_session.commit()
        return u

    @staticmethod
    def checkUser(username: str) -> bool:
        # TODO: Add in TAS check
        pass

    @staticmethod
    def getUser(username: str, tenant: str) -> User:
        return db_session.query(User)\
            .filter(User.username == username)\
            .filter(User.tenant_id == tenant)\
            .first()

    @staticmethod
    def canAccess(user: User, projectId: int) -> bool:
        up = db_session.query(ProjectUser)\
            .filter(ProjectUser.user_id == user.id)\
            .filter(Project.tenant_id == user.tenant_id)\
            .filter(ProjectUser.project_id == projectId).first()
        if up:
            return True
        return False

    @staticmethod
    def setJWT(user: User, token: str) -> None:
        user.jwt = token
        db_session.commit()
