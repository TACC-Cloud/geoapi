from geoapi.models import User, Project, ProjectUser


class UserService:

    @staticmethod
    def create(database_session, username: str, tenant: str, jwt: str = None) -> User:
        """

        :rtype: User
        """
        u = User(username=username, tenant_id=tenant)
        if jwt:
            u.jwt = jwt
        database_session.add(u)
        database_session.commit()
        return u

    @staticmethod
    def getOrCreateUser(database_session, username: str, tenant: str) -> User:
        user = UserService.getUser(database_session, username, tenant)
        if not user:
            user = UserService.create(database_session, username, tenant)
        return user

    @staticmethod
    def getUser(database_session, username: str, tenant: str) -> User:
        return database_session.query(User)\
            .filter(User.username == username)\
            .filter(User.tenant_id == tenant)\
            .first()

    @staticmethod
    def get(database_session, userId: int) -> User:
        return database_session.query(User).get(userId)

    @staticmethod
    def canAccess(database_session, user: User, projectId: int) -> bool:
        up = database_session.query(ProjectUser)\
            .join(Project)\
            .filter(ProjectUser.user_id == user.id)\
            .filter(Project.tenant_id == user.tenant_id)\
            .filter(ProjectUser.project_id == projectId).one_or_none()
        if up:
            return True
        return False

    @staticmethod
    def is_admin_or_creator(database_session, user: User, projectId: int) -> bool:
        up = database_session.query(ProjectUser) \
            .join(Project) \
            .filter(ProjectUser.user_id == user.id) \
            .filter(Project.tenant_id == user.tenant_id) \
            .filter(ProjectUser.project_id == projectId).one_or_none()
        if up:
            return up.admin or up.creator
        return False

    @staticmethod
    def setJWT(database_session, user: User, token: str) -> None:
        user.jwt = token
        database_session.commit()
