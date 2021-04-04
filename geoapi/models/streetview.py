from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from geoapi.db import Base
import uuid

class Streetview(Base):
    __tablename__ = 'streetview'

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    path = Column(String(), nullable=True, index=True)
    system_id = Column(String(), nullable=True, index=True)
    sequences = relationship('StreetviewSequence', cascade="all, delete-orphan")

    user = relationship('User')

    def __repr__(self):
        return '<Streetview(id={})>'.format(self.id)


class StreetviewSequence(Base):
    __tablename__ = 'streetview_sequence'

    id = Column(Integer, primary_key=True)
    streetview_id = Column(ForeignKey('streetview.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    service = Column(String(), index=True)
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    bbox = Column(String(), index=True)
    sequence_key = Column(String(), index=True)
    streetview = relationship('Streetview')

    def __repr__(self):
        return '<StreetviewSequence(id={})>'.format(self.id)
