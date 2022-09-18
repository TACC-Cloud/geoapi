from sqlalchemy import (
    Column, Integer, String,
    ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from geoapi.db import Base


class TileServer(Base):
    __tablename__ = 'tile_servers'
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    name = Column(String(), nullable=False)
    type = Column(String(), nullable=False)
    url = Column(String(), nullable=False)
    attribution = Column(String(), nullable=False)
    tileOptions = Column(JSONB, default={})
    uiOptions = Column(JSONB, default={})

    project = relationship('Project')

    def __repr__(self):
        return '<TileServer(id={})>'.format(self.id)
