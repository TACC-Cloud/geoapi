from sqlalchemy import and_
from sqlalchemy.sql import func

from datetime import datetime, timezone

from geoapi.models.public_system_access_check import PublicSystemAccessCheck
from geoapi.models import Task, TaskStatus

from sqlalchemy.orm import Session


class PublicSystemAccessService:
    """Service for managing checking if files are accessible from public systems."""

    @staticmethod
    def start_check(
        db_session: "Session", project_id: int, celery_task_uuid: str
    ) -> PublicSystemAccessCheck:
        check = (
            db_session.query(PublicSystemAccessCheck)
            .filter(PublicSystemAccessCheck.project_id == project_id)
            .first()
        )

        task = Task(
            process_id=celery_task_uuid,
            status=TaskStatus.QUEUED,
            description="Refreshing public status",
            project_id=project_id,
        )
        db_session.add(task)
        db_session.flush()  # Flush to get the task.id

        if check:
            check.started_at = datetime.now(timezone.utc)
            check.completed_at = None
            check.task_id = task.id
        else:
            check = PublicSystemAccessCheck(project_id=project_id, task_id=task.id)
            db_session.add(check)

        db_session.commit()
        return check

    @staticmethod
    def complete_check(db_session: "Session", project_id: int) -> None:
        """Mark the check as completed."""
        check = PublicSystemAccessService.get(db_session, project_id)
        if not check:
            raise ValueError(f"No check found for project {project_id}")
        check.completed_at = func.now()
        db_session.commit()

    @staticmethod
    def has_running_check(db_session: Session, project_id: int) -> bool:
        """Check if there's currently a running refresh for this project."""
        running = (
            db_session.query(PublicSystemAccessCheck)
            .filter(
                and_(
                    PublicSystemAccessCheck.project_id == project_id,
                    PublicSystemAccessCheck.started_at.isnot(None),
                    PublicSystemAccessCheck.completed_at.is_(None),
                )
            )
            .first()
        )
        return running is not None

    @staticmethod
    def get(db_session: "Session", project_id: int) -> PublicSystemAccessCheck | None:
        """Get the currently running refresh for this project."""
        return (
            db_session.query(PublicSystemAccessCheck)
            .filter(PublicSystemAccessCheck.project_id == project_id)
            .first()
        )
