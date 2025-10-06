from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import mapped_column, validates
from litestar.dto import dto_field
from enum import Enum
from geoapi.db import Base


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    ERROR = "ERROR"
    COMPLETED = "COMPLETED"


class Task(Base):
    __tablename__ = "tasks"

    id = mapped_column(Integer, primary_key=True)
    process_id = mapped_column(String(), nullable=False, info=dto_field("private"))
    status = mapped_column(String())
    description = mapped_column(String())
    project_id = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
        nullable=True,
    )
    latest_message = mapped_column(String(), nullable=True)
    created = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated = mapped_column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return (
            f"<Task(id={self.id} process_id={self.process_id} status={self.status} "
            f"description={self.description} updated={self.updated} )>"
        )

    @validates("status")
    def _validate_status(self, _key, value: str) -> str:
        if value not in {s.value for s in TaskStatus}:
            raise ValueError(f"Invalid task status: {value}")
        return value
