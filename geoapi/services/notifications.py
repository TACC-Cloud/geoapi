from typing import List, AnyStr, Dict

from geoapi.models import Notification
from geoapi.models import User
from geoapi.db import db_session
from geoapi.log import logging

logger = logging.getLogger(__file__)


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
    def get(user: User, filters: Dict) -> List[Notification]:
        q = db_session.query(Notification) \
            .filter(Notification.username == user.username) \
            .filter(Notification.tenant_id == user.tenant_id)
        if filters.get("startDate"):
            q = q.filter(Notification.created > filters.get("startDate"))
        return q.order_by(Notification.created.desc()) \
                .limit(100).all()

    @staticmethod
    def create(user: User, status: AnyStr, message: AnyStr) -> Notification:
        note = Notification(
            username=user.username,
            tenant_id=user.tenant_id,
            status=status,
            message=message
        )
        try:
            db_session.add(note)
            db_session.commit()
            return note
        except Exception:
            db_session.rollback()
            raise
