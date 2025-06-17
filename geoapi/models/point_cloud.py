from sqlalchemy import Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from geoapi.db import Base


class PointCloud(Base):
    __tablename__ = "point_clouds"

    id = mapped_column(Integer, primary_key=True)
    uuid = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    feature_id = mapped_column(
        ForeignKey("features.id", ondelete="SET NULL", onupdate="CASCADE"), index=True
    )
    project_id = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE", onupdate="CASCADE"), index=True
    )
    task_id = mapped_column(ForeignKey("tasks.id"), index=True)
    description = mapped_column(String)
    conversion_parameters = mapped_column(String)
    files_info = mapped_column(JSON)
    path = mapped_column(String(), nullable=False)
    tenant_id = mapped_column(String, nullable=False)
    created = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated = mapped_column(DateTime(timezone=True), onupdate=func.now())
    project = relationship("Project", overlaps="point_clouds")
    feature = relationship("Feature", lazy="joined")
    task = relationship("Task", lazy="joined")

    def __repr__(self):
        return (
            f"<PointCloud(id={self.id} description={self.description}) "
            f"project_id={self.project_id}  feature_id={self.feature_id} task={self.task_id}>"
            f"path={self.path} updated={self.updated}"
        )
