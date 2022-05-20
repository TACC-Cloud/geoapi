from sqlalchemy import (
    Column, Integer, String, Boolean,
    ForeignKey, DateTime, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoapi.db import Base


class ObservableDataProject(Base):
    __tablename__ = 'observable_data_projects'
    __table_args__ = (
        UniqueConstraint('system_id', 'path'),
    )
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    system_id = Column(String, nullable=False)
    path = Column(String, nullable=False, default="RApp")
    watch_content = Column(Boolean, default=True)
    project = relationship("Project")
