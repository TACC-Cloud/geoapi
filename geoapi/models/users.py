from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoapi.db import Base


class User(Base):

    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String)
    created = Column(DateTime(timezone=True), server_default=func.now())
    projects = relationship('Project',
                 secondary='projects_users',
                 back_populates='users', lazy="joined")


    def __repr__(self):
        return '<Project(id={})>'.format(self.id)
