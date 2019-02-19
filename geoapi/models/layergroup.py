from geoapi.db import Base
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

class LayerGroup(Base):
    __tablename__ = 'layergroups'

    project_id = Column(Integer, ForeignKey('projects.id'))
    id = Column(Integer, primary_key=True)
    name = Column(String(128))
    description = Column(String, nullable=True)
    created = Column(DateTime(timezone=True), server_default=func.now())

    features = relationship('Feature', cascade="all, delete-orphan")

    def __repr__(self):
        return '<LayerGroup(id={})>'.format(self.id)