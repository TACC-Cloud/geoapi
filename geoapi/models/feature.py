from geoapi.db import Base
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, Boolean, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

class Feature(Base):
    __tablename__ = 'features'
    id = Column(Integer, primary_key=True)
    layergroup_id = Column(ForeignKey('layergroups.id'), index=True)
    layergroup = relationship("LayerGroup", back_populates="features")
    the_geom = Column(Geometry(geometry_type='GEOMETRY', srid=4326))
    extra = Column(JSONB)
