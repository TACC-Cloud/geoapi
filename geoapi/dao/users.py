from geoapi.models import User, Project
from geoapi.db import db_session
from typing import List

class UserDAO():

    @staticmethod
    def create(username: str) -> None:
        p = User(username=username)
        db_session.add(p)
        db_session.commit()

    @staticmethod
    def getUser(username: str)-> User:
        return db_session.query(User).filter(User.username == username).first()

    @staticmethod
    def projectsForUser(username: str)->List[Project]:
        user = db_session.query(User).filter(User.username == username).first()
        if not user:
            return []
        return user.projects
