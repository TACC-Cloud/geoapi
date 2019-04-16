import uuid
from sqlalchemy import (
    Column, Integer, String, Numeric,
    ForeignKey, Boolean, Index
)
import shapely
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from geoalchemy2.shape import from_shape, to_shape
from geoapi.db import Base


class Overlay(Base):
    __tablename__ = 'overlays'
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    path = Column(String(), nullable=False)
    minLat = Column(Numeric(), nullable=False)
    minLon = Column(Numeric(), nullable=False)
    maxLat = Column(Numeric(), nullable=False)
    maxLon = Column(Numeric(), nullable=False)
    label = Column(String(), nullable=False)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)

    project = relationship('Project')

    def __repr__(self):
        return '<Overlay(id={})>'.format(self.id)
