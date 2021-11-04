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


    @staticmethod
    def getAllProgress(user: User) -> List[ProgressNotification]:
        return db_session.query(ProgressNotification) \
            .filter(ProgressNotification.user_id == user.id) \
            .filter(ProgressNotification.tenant_id == user.tenant_id)\
            .order_by(ProgressNotification.created.desc()) \
            .limit(100)\
            .all()


    def getAllProgressUUID(user: User, task_uuid: UUID) -> List[ProgressNotification]:
        return db_session.query(ProgressNotification) \
            .filter(ProgressNotification.user_id == user.id)\
            .filter(ProgressNotification.tenant_id == user.tenant_id)\
            .filter(ProgressNotification.uuid == task_uuid) \
            .order_by(ProgressNotification.created.desc()) \
            .limit(100)\
            .all()


    @staticmethod
    def getProgress(user: User) -> List[ProgressNotification]:
        q = db_session.query(ProgressNotification) \
            .filter(ProgressNotification.user_id == user.id) \
            .filter(ProgressNotification.tenant_id == user.tenant_id)
        return q.order_by(ProgressNotification.created.desc()) \
                .limit(100).all()

    @staticmethod
    def getProgressUUID(task_uuid: UUID) -> ProgressNotification:
        return db_session.query(ProgressNotification) \
                         .filter(ProgressNotification.uuid == task_uuid) \
                         .first()

    @staticmethod
    def getProgressStatus(status: str) -> List[ProgressNotification]:
        return db_session.query(ProgressNotification) \
                         .filter(ProgressNotification.status == status) \
                         .all()

    @staticmethod
    def createProgress(user: User, status: AnyStr, message: AnyStr, task_uuid: UUID, logs: List=None) -> ProgressNotification:
        note = ProgressNotification(
            user_id=user.id,
            tenant_id=user.tenant_id,
            uuid=task_uuid,
            status=status,
            progress=0,
            message=message,
            logs=logs
        )
        try:
            db_session.add(note)
            db_session.commit()
            return note
        except Exception:
            db_session.rollback()
            raise


    @staticmethod
    def updateProgress(task_uuid: UUID, status: AnyStr=None, message: AnyStr=None, progress: int=None, logItem: Dict=None):
        note = db_session.query(ProgressNotification) \
                         .filter(ProgressNotification.uuid == task_uuid) \
                         .first()
        try:
            if status is not None:
                note.status = status
            if message is not None:
                note.message = message
            if progress is not None:
                note.progress = progress
            if logItem is not None:
                new_log = note.logs
                new_log.update(logItem)
                note.extraData = new_log
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise


    @staticmethod
    def deleteProgress(task_uuid: UUID):
        notes = db_session.query(ProgressNotification) \
                         .filter(ProgressNotification.uuid == task_uuid)
        try:
            for i in notes:
                db_session.delete(i)
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise


    @staticmethod
    def deleteAllDoneProgress():
        note = db_session.query(ProgressNotification) \
                         .filter(ProgressNotification.status == 'success')
        try:
            for pn in note:
                db_session.delete(pn)
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
