import uuid
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, Boolean, Index, DateTime
)
import shapely
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from geoalchemy2.shape import from_shape, to_shape
from geoapi.db import Base
from typing import TypeVar


class Feature(Base):
    __tablename__ = 'features'
    __table_args__ = (
        Index('ix_features_properties', 'properties', postgresql_using="gin"),
    )

    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    the_geom = Column(Geometry(geometry_type='GEOMETRY', srid=4326), nullable=False)
    properties = Column(JSONB, default={})
    styles = Column(JSONB, default={})
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    assets = relationship("FeatureAsset", cascade="all, delete-orphan", lazy="joined")
    project = relationship("Project")

    def __repr__(self):
        return '<Feature(id={})>'.format(self.id)

    @classmethod
    def fromGeoJSON(cls, data: dict):
        shp = shapely.geometry.shape(data["geometry"])
        feat = cls()
        feat.the_geom = from_shape(shp, srid=4326)
        feat.properties = data.get("properties")
        feat.styles = data.get("styles")
        return feat

    @property
    def geometry(self):
        """

        :return: Dict
        """
        return shapely.geometry.mapping(to_shape(self.the_geom))


class FeatureAsset(Base):
    __tablename__ = 'feature_assets'
    id = Column(Integer, primary_key=True)
    feature_id = Column(ForeignKey('features.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    path = Column(String(), nullable=False)
    original_name = Column(String(), nullable=True)
    display_path = Column(String(), nullable=True, index=True)
    asset_type = Column(String(), nullable=False, default="image")
    feature = relationship('Feature')

    def __repr__(self):
        return '<FeatureAsset(id={})>'.format(self.id)
