from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import relationship, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from geoapi.db import Base


class TileServer(Base):
    __tablename__ = "tile_servers"
    id = mapped_column(Integer, primary_key=True)
    project_id = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE", onupdate="CASCADE"), index=True
    )
    name = mapped_column(String(), nullable=False)
    type = mapped_column(String(), nullable=False)
    url = mapped_column(String(), nullable=False)
    attribution = mapped_column(String(), nullable=False)
    tileOptions = mapped_column(JSONB, default={})
    uiOptions = mapped_column(JSONB, default={})

    project = relationship("Project")

    def __repr__(self):
        return "<TileServer(id={})>".format(self.id)
