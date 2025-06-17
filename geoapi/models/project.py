import uuid
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from geoapi.db import Base
from geoapi.models.users import User


class ProjectUser(Base):
    __tablename__ = "projects_users"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    creator = Column(Boolean, nullable=False, default=False)
    admin = Column(Boolean, nullable=False, default=False)
    project = relationship(
        "Project", backref=backref("project_users", cascade="all, delete-orphan")
    )
    user = relationship("User", viewonly=True, back_populates="project_users")

    def __repr__(self):
        return f"<ProjectUser(user_id={self.user_id}, project_id={self.project_id}, admin={self.admin}, creator={self.creator})>"


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    tenant_id = Column(String, nullable=False)
    # associated tapis system id
    system_id = Column(String, nullable=True)
    # associated tapis system path
    system_path = Column(String, nullable=True)
    # associated tapis system file
    system_file = Column(String, nullable=True)
    name = Column(String, nullable=False)
    description = Column(String)
    public = Column(Boolean, default=False)
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), onupdate=func.now())
    features = relationship("Feature", cascade="all, delete-orphan")

    users = relationship(
        "User",
        secondary="projects_users",
        back_populates="projects",
        overlaps="project,project_users",
    )
    point_clouds = relationship("PointCloud", cascade="all, delete-orphan")

    # watch content of tapis directory location (system_id and system_path)
    watch_content = Column(Boolean, default=False)

    # watch user of tapis system (system_id)
    watch_users = Column(Boolean, default=False)

    def __repr__(self):
        return (
            f"<Project(id={self.id}, uuid={self.uuid}, tenant_id='{self.tenant_id}', "
            f"system_id='{self.system_id}', system_path='{self.system_path}', "
            f"system_file='{self.system_file}', name='{self.name}', "
            f"description='{self.description}', public={self.public}, "
            f"created={self.created}, updated={self.updated}, "
            f"watch_content={self.watch_content}, watch_users={self.watch_users})>"
        )
