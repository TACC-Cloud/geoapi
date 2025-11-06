from sqlalchemy import Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy.sql import func
from geoapi.db import Base


class FileLocationCheck(Base):
    """
    Tracks when a project's files were checked for location (including if accessible to public)

    This model stores metadata about this public-system-access checks. Individual file status
    is tracked via FeatureAsset.is_on_public_system and FeatureAsset.last_public_system_check.

    Note just one check per file. It can be re-run, but we only keep info about a
    single (i.e. current or last) check.
    """

    __tablename__ = "public_system_access_checks"

    id = mapped_column(Integer, primary_key=True)
    project_id = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
        nullable=False,
        unique=True,
    )
    task_id = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # Timestamps
    started_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)

    total_files: Mapped[int | None] = mapped_column(Integer, default=0)
    files_checked: Mapped[int | None] = mapped_column(Integer, default=0)
    files_failed: Mapped[int | None] = mapped_column(Integer, default=0)

    # Relationships
    project = relationship("Project")
    task = relationship("Task")

    def __repr__(self):
        return (
            f"<PublicCheck(id={self.id}, project_id={self.project_id}, task_id={self.task_id}"
            f"started_at={self.started_at}) completed_at={self.completed_at}>"
        )
