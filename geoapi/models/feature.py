import uuid
from sqlalchemy import Integer, String, ForeignKey, Index, DateTime
import shapely
from litestar.dto import dto_field
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from geoalchemy2.shape import from_shape, to_shape
from geoapi.db import Base
from geoapi.models.file_location_tracking_mixin import FileLocationTrackingMixin
from geoapi.utils import geometries


class Feature(Base):
    __tablename__ = "features"
    __table_args__ = (
        Index("ix_features_properties", "properties", postgresql_using="gin"),
    )

    id = mapped_column(Integer, primary_key=True)
    project_id = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE", onupdate="CASCADE"), index=True
    )
    the_geom: Mapped[shapely.GeometryType] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326),
        info=dto_field("private"),
    )  # Spatial index included by default
    properties = mapped_column(JSONB, default={})
    styles = mapped_column(JSONB, default={})
    created_date = mapped_column(DateTime(timezone=True), server_default=func.now())
    assets = relationship("FeatureAsset", cascade="all, delete-orphan", lazy="joined")
    project = relationship("Project", overlaps="features")

    def __repr__(self):
        return "<Feature(id={})>".format(self.id)

    @classmethod
    def fromGeoJSON(cls, data: dict):
        shp = shapely.geometry.shape(data["geometry"])
        feat = cls()
        # Some features have Z-axis data, the epsg:4326 index doesn't like that
        # TODO: This might be better to handle in Postgres itself on insert
        feat.the_geom = from_shape(geometries.convert_3D_2D(shp), srid=4326)
        feat.properties = data.get("properties")
        feat.styles = data.get("styles")
        return feat

    @property
    def geometry(self) -> dict:
        """

        :return: Dict
        """
        return shapely.geometry.mapping(to_shape(self.the_geom))


class FeatureAsset(Base, FileLocationTrackingMixin):
    __tablename__ = "feature_assets"
    id = mapped_column(Integer, primary_key=True)
    feature_id = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE", onupdate="CASCADE"), index=True
    )
    uuid = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    # system or project id or both
    path = mapped_column(String(), nullable=False)
    display_path = mapped_column(String(), nullable=True)

    # Original source file location
    original_name = mapped_column(String(), nullable=True)

    # Note: original_system, original_path, current_system, current_path,
    #       is_on_public_system, and last_public_system_check are inherited
    #       from FileLocationTrackingMixin

    asset_type = mapped_column(String(), nullable=False, default="image")
    feature = relationship("Feature", overlaps="assets")

    def __repr__(self):
        return "<FeatureAsset(id={})>".format(self.id)
