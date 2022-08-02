import uuid
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, Boolean, DateTime
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from geoapi.db import Base


class ProjectUser(Base):
    __tablename__ = 'projects_users'

    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete="CASCADE"), primary_key=True)
    creator = Column(Boolean, default=False)
    admin = Column(Boolean, default=False)
    project = relationship('Project', backref=backref('project_users', cascade="all, delete-orphan"))


class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    tenant_id = Column(String, nullable=False)
    system_id = Column(String, nullable=True)
    system_path = Column(String, nullable=True)
    system_file = Column(String, nullable=True)
    name = Column(String, nullable=False)
    description = Column(String)
    public = Column(Boolean, default=False)
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), onupdate=func.now())
    features = relationship('Feature', cascade="all, delete-orphan")

    users = relationship('User',
                         secondary='projects_users',
                         back_populates='projects')
    point_clouds = relationship('PointCloud', cascade="all, delete-orphan")

    def __repr__(self):
        return '<Project(id={})>'.format(self.id)
