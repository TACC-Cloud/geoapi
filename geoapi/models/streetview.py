from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoapi.db import Base

class Streetview(Base):
    __tablename__ = 'streetview'

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    path = Column(String(), nullable=True, index=True)
    systemId = Column(String(), nullable=True, index=True)
    mapillary = Column(Boolean(), nullable=True, index=True)
    google = Column(Boolean(), nullable=True, index=True)
    sequenceKey = Column(String(), nullable=True, index=True)

    user = relationship('User')

    def __repr__(self):
        return '<Streetview(id={})>'.format(self.id)
