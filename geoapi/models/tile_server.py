import uuid
from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean,
    ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from geoapi.db import Base


class TileServer(Base):
    __tablename__ = 'tile_servers'
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    name = Column(String(), nullable=False)
    type = Column(String(), nullable=False)
    url = Column(String(), nullable=False)
    attribution = Column(String(), nullable=False)
    opacity = Column(Numeric(), nullable=False)
    zIndex = Column(Numeric(), nullable=True)
    maxZoom = Column(Numeric(), nullable=True)
    minZoom = Column(Numeric(), nullable=True)
    isActive = Column(Boolean(), nullable=False)
    wmsLayers = Column(String())
    wmsFormat = Column(String())
    wmsParams = Column(String())

    project = relationship('Project')

    def __repr__(self):
        return '<TileServer(id={})>'.format(self.id)
