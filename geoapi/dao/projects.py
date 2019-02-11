from geoapi.models import Project, User, LayerGroup
from geoapi.db import db_session
from typing import List

class ProjectsDAO():

    @staticmethod
    def create(data, user: User) -> Project:
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
        for p in u.projects:
            print(p.layergroups)
        return u.projects

    @staticmethod
    def get(projectId: int) -> Project:
        return db_session.query(Project)\
            .filter(Project.id == projectId).first()

    def update(self, projectId, data):
        pass

    def delete(self, projectId):
        pass

    @staticmethod
    def addUser(username: str):
        pass
