import uuid
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, Boolean, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from geoapi.db import Base


class Feature(Base):
    __tablename__ = 'features'
    id = Column(Integer, primary_key=True)
    layergroup_id = Column(ForeignKey('layergroups.id'), index=True)
    the_geom = Column(Geometry(geometry_type='GEOMETRY', srid=4326))
    extra = Column(JSONB)
    assets = relationship("FeatureAsset", cascade="all, delete-orphan")

    def __repr__(self):
        return '<Feature(id={})>'.format(self.id)


class FeatureAsset(Base):
    __tablename__ = 'feature_assets'
    id = Column(Integer, primary_key=True)
    feature_id = Column(ForeignKey('features.id'), index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)

    def __repr__(self):
        return '<FeatureAsset(id={})>'.format(self.id)