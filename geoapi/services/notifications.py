from typing import List, AnyStr

from geoapi.models import Notification
from geoapi.models import User
from geoapi.db import db_session

class NotificationsService:

    @staticmethod
    def getAll(user: User) -> List[Notification]:
        return db_session.query(Notification) \
            .filter(Notification.username == user.username)\
            .filter(Notification.tenant_id == user.tenant_id)\
            .order_by(Notification.created.desc()) \
            .limit(100)\
            .all()

    @staticmethod
    def create(user: User, status: AnyStr, message: AnyStr) -> Notification:
        note = Notification(
            username=user.username,
            tenant_id=user.tenant_id,
            status=status,
            message=message
        )
        db_session.add(note)
        db_session.commit()
        return note
