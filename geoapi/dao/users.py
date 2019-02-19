from geoapi.models import User, Project, ProjectUser
from geoapi.db import db_session
from typing import List

class UserDAO():

    @staticmethod
    def create(username: str) -> User:
        """

        :rtype: User
        """
        u = User(username=username)
        db_session.add(u)
        db_session.commit()
        return u

    @staticmethod
    def getUser(username: str)-> User:
        return db_session.query(User).filter(User.username == username).first()

    @staticmethod
    def projectsForUser(username: str)->List[Project]:
        user = db_session.query(User).filter(User.username == username).first()
        if not user:
            return []
        return user.projects

    @staticmethod
    def canAccess(user: User, projectId: int) -> bool:
        up = db_session.query(ProjectUser)\
            .filter(ProjectUser.user_id == user.id)\
            .filter(ProjectUser.project_id == projectId).first()
        if up:
            return True
        return False