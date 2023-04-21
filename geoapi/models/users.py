from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoapi.db import Base


class User(Base):

    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    tenant_id = Column(String, nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now())
    jwt = Column(String())
    streetviews = relationship('Streetview', cascade="all, delete-orphan")
    projects = relationship('Project',
                            secondary='projects_users',
                            back_populates='users', lazy="joined",
                            overlaps="project,project_users")

    def __repr__(self):
        return '<User(uname={}, id={})>'.format(self.username, self.id)
