import uuid
from sqlalchemy import Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from geoapi.db import Base


class Overlay(Base):
    __tablename__ = "overlays"
    id = mapped_column(Integer, primary_key=True)
    project_id = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE", onupdate="CASCADE"), index=True
    )
    path = mapped_column(String(), nullable=False)
    minLat = mapped_column(Numeric(), nullable=False)
    minLon = mapped_column(Numeric(), nullable=False)
    maxLat = mapped_column(Numeric(), nullable=False)
    maxLon = mapped_column(Numeric(), nullable=False)
    label = mapped_column(String(), nullable=False)
    uuid = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)

    project = relationship("Project")

    def __repr__(self):
        return "<Overlay(id={})>".format(self.id)
