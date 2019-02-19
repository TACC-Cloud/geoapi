from geoapi.models import Project, User, LayerGroup
from geoapi.db import db_session
from typing import List


class ProjectsDAO:

    @staticmethod
    def create(data: dict, user: User) -> Project:
        project = Project(**data)
        lg = LayerGroup(name="Layer 1")
        project.layergroups.append(lg)
        project.users.append(user)
        db_session.add(project, lg)
        db_session.commit()
        return project

    @staticmethod
    def list(username: str) -> List[Project]:
        u = db_session.query(User).filter(User.username == username).first()
        if not u:
            return []
        return u.projects

    @staticmethod
    def get(projectId: int) -> Project:

        return db_session.query(Project)\
            .filter(Project.id == projectId).first()

    @staticmethod
    def update(projectId: int, data) -> Project:
        pass

    @staticmethod
    def delete(projectId: int) -> None:
        db_session.query(Project) \
            .filter(Project.id == projectId).delete()
        db_session.commit()

    @staticmethod
    def addUserToProject(projectId: int, username: str) -> None:
        proj = db_session.query(Project) \
            .filter(Project.id == projectId).first()
        user = db_session.query(User) \
                .filter(User.username == username).first()
        proj.users.append(user)
        db_session.commit()

    @staticmethod
    def removeUserFromProject(projectId: int, username: str) -> None:
        proj = db_session.query(Project) \
            .filter(Project.id == projectId).first()
        user = db_session.query(User) \
            .filter(User.username == username).first()
        proj.users.remove(user)
        db_session.commit()