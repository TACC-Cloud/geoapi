import uuid
from sqlalchemy import Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship, backref, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
from geoapi.db import Base


class ProjectUser(Base):
    __tablename__ = "projects_users"

    user_id = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    project_id = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    creator = mapped_column(Boolean, nullable=False, default=False)
    admin = mapped_column(Boolean, nullable=False, default=False)
    project = relationship(
        "Project", backref=backref("project_users", cascade="all, delete-orphan")
    )
    user = relationship("User", viewonly=True, back_populates="project_users")

    def __repr__(self):
        return f"<ProjectUser(user_id={self.user_id}, project_id={self.project_id}, admin={self.admin}, creator={self.creator})>"


class Project(Base):
    __tablename__ = "projects"

    id = mapped_column(Integer, primary_key=True)
    uuid = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    tenant_id = mapped_column(String, nullable=False)
    # associated DesignSafe project
    designsafe_project_id = mapped_column(String, nullable=True)
    # associated tapis system id
    system_id = mapped_column(String, nullable=True)
    # associated tapis system path
    system_path = mapped_column(String, nullable=True)
    # associated tapis system file
    system_file = mapped_column(String, nullable=True)
    name = mapped_column(String, nullable=False)
    description = mapped_column(String)
    public = mapped_column(Boolean, default=False)
    created = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated = mapped_column(DateTime(timezone=True), onupdate=func.now())
    features = relationship("Feature", cascade="all, delete-orphan")

    users = relationship(
        "User",
        secondary="projects_users",
        back_populates="projects",
        overlaps="project,project_users",
    )
    point_clouds = relationship("PointCloud", cascade="all, delete-orphan")

    # watch content of tapis directory location (system_id and system_path)
    watch_content = mapped_column(Boolean, default=False)

    # watch user of tapis system (system_id)
    watch_users = mapped_column(Boolean, default=False)

    _deletable: bool = False

    @hybrid_property
    def deletable(self):
        return getattr(self, "_deletable", False)

    @deletable.setter
    def deletable(self, value: bool):
        self._deletable = value

    def __repr__(self):
        return (
            f"<Project(id={self.id}, uuid={self.uuid}, tenant_id='{self.tenant_id}', "
            f"system_id='{self.system_id}', system_path='{self.system_path}', "
            f"system_file='{self.system_file}', name='{self.name}', "
            f"description='{self.description}', public={self.public}, "
            f"created={self.created}, updated={self.updated}, "
            f"watch_content={self.watch_content}, watch_users={self.watch_users})>"
        )
