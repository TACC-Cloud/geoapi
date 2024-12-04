from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoapi.db import Base


# Deprecated; Replaced by watch_user and watch_content of Project table. See https://tacc-main.atlassian.net/browse/WG-377
class ObservableDataProject(Base):
    __tablename__ = "observable_data_projects"
    id = Column(Integer, primary_key=True)
    project_id = Column(
        ForeignKey("projects.id", ondelete="CASCADE", onupdate="CASCADE"), index=True
    )
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    system_id = Column(String, nullable=False)
    path = Column(String, nullable=False, default="RApp")
    watch_content = Column(Boolean, default=True)
    project = relationship("Project")
