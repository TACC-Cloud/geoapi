from typing import List, AnyStr, Dict

from geoapi.models import Notification, ProgressNotification
from geoapi.models import User
from uuid import UUID
from geoapi.log import logging

logger = logging.getLogger(__file__)


class NotificationsService:

    @staticmethod
    def getAll(database_session, user: User) -> List[Notification]:
        return (
            database_session.query(Notification)
            .filter(Notification.username == user.username)
            .filter(Notification.tenant_id == user.tenant_id)
            .order_by(Notification.created.desc())
            .limit(100)
            .all()
        )

    @staticmethod
    def get(database_session, user: User, filters: Dict) -> List[Notification]:
        q = (
            database_session.query(Notification)
            .filter(Notification.username == user.username)
            .filter(Notification.tenant_id == user.tenant_id)
        )
        if filters.get("startDate"):
            q = q.filter(Notification.created > filters.get("startDate"))
        return q.order_by(Notification.created.desc()).limit(100).all()

    @staticmethod
    def create(
        database_session, user: User, status: AnyStr, message: AnyStr
    ) -> Notification:
        note = Notification(
            username=user.username,
            tenant_id=user.tenant_id,
            status=status,
            message=message,
        )
        try:
            database_session.add(note)
            database_session.commit()
            return note
        except Exception:
            database_session.rollback()
            raise

    @staticmethod
    def getProgress(database_session, user: User) -> List[ProgressNotification]:
        q = (
            database_session.query(ProgressNotification)
            .filter(ProgressNotification.user_id == user.id)
            .filter(ProgressNotification.tenant_id == user.tenant_id)
        )
        return q.order_by(ProgressNotification.created.desc()).limit(100).all()

    @staticmethod
    def getProgressUUID(database_session, task_uuid: UUID) -> ProgressNotification:
        return (
            database_session.query(ProgressNotification)
            .filter(ProgressNotification.uuid == task_uuid)
            .first()
        )

    @staticmethod
    def getProgressStatus(database_session, status: str) -> List[ProgressNotification]:
        return (
            database_session.query(ProgressNotification)
            .filter(ProgressNotification.status == status)
            .all()
        )

    @staticmethod
    def createProgress(
        database_session,
        user: User,
        status: AnyStr,
        message: AnyStr,
        task_uuid: UUID,
        logs: Dict = None,
    ) -> ProgressNotification:
        note = ProgressNotification(
            user_id=user.id,
            tenant_id=user.tenant_id,
            uuid=task_uuid,
            status=status,
            progress=0,
            message=message,
            logs=logs,
        )
        database_session.add(note)
        database_session.commit()
        return note

    @staticmethod
    def updateProgress(
        database_session,
        task_uuid: UUID,
        status: AnyStr = None,
        message: AnyStr = None,
        progress: int = None,
        logItem: Dict = None,
    ):
        note = (
            database_session.query(ProgressNotification)
            .filter(ProgressNotification.uuid == task_uuid)
            .first()
        )
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
        database_session.commit()

    @staticmethod
    def deleteProgress(database_session, task_uuid: UUID):
        notes = database_session.query(ProgressNotification).filter(
            ProgressNotification.uuid == task_uuid
        )
        for i in notes:
            database_session.delete(i)
        database_session.commit()

    @staticmethod
    def deleteAllDoneProgress(database_session):
        note = database_session.query(ProgressNotification).filter(
            ProgressNotification.status == "success"
        )
        for pn in note:
            database_session.delete(pn)
        database_session.commit()
