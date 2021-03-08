from typing import List, AnyStr, Dict

from geoapi.models import Notification, ProgressNotification
from geoapi.models import User
from uuid import UUID
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

    # TODO: Just make this part of Task
    @staticmethod
    def getAllProgress(user: User, task_uuid: UUID) -> List[ProgressNotification]:
        return db_session.query(ProgressNotification) \
            .filter(ProgressNotification.username == user.username)\
            .filter(ProgressNotification.tenant_id == user.tenant_id)\
            .filter(ProgressNotification.uuid == task_uuid) \
            .order_by(ProgressNotification.created.desc()) \
            .limit(100)\
            .all()

    @staticmethod
    def getProgress(user: User, filters: Dict, task_uuid: UUID) -> List[ProgressNotification]:
        q = db_session.query(ProgressNotification) \
            .filter(ProgressNotification.username == user.username) \
            .filter(ProgressNotification.tenant_id == user.tenant_id) \
            .filter(ProgressNotification.uuid == task_uuid)
        if filters.get("startDate"):
            q = q.filter(ProgressNotification.created > filters.get("startDate"))
        return q.order_by(ProgressNotification.created.desc()) \
                .limit(100).all()

    @staticmethod
    def createProgress(user_id: int, tenant_id: str, status: AnyStr, message: AnyStr, task_uuid: UUID) -> ProgressNotification:
        note = ProgressNotification(
            user_id=user_id,
            tenant_id=tenant_id,
            uuid=task_uuid,
            status=status,
            progress=0,
            message=message
        )
        try:
            db_session.add(note)
            db_session.commit()
            return note
        except Exception:
            db_session.rollback()
            raise


    @staticmethod
    def updateProgress(status: AnyStr, message: AnyStr, task_uuid: UUID, progress: int):
        note = db_session.query(ProgressNotification) \
                         .filter(ProgressNotification.uuid == task_uuid)
        try:
            note.status = status
            note.message = message
            note.progress = progress
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
