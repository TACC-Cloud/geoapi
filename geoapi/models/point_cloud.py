from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, Boolean, Index, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from geoapi.db import Base


class PointCloud(Base):
    __tablename__ = 'point_clouds'

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    feature_id = Column(ForeignKey('features.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    project_id = Column(ForeignKey('projects.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    task_id = Column(ForeignKey('tasks.id'), index=True)
    description = Column(String)
    conversion_parameters = Column(String)
    path = Column(String(), nullable=False)
    tenant_id = Column(String, nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), onupdate=func.now())
    project = relationship("Project")
    feature = relationship("Feature", cascade="all", lazy="joined")
    task = relationship("Task", lazy="joined")

    def __repr__(self):
        return '<PointCloud(id={})>'.format(self.id)
