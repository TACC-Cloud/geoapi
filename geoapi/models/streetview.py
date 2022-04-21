from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from geoapi.db import Base

class Streetview(Base):
    __tablename__ = 'streetview'

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    user = relationship('User')
    token = Column(String())
    service = Column(String())
    service_user = Column(String())
    organizations = relationship('StreetviewOrganization', cascade="all, delete-orphan")
    instances = relationship('StreetviewInstance', cascade="all, delete-orphan")

    def __repr__(self):
        return '<Streetview(id={})>'.format(self.id)

class StreetviewOrganization(Base):
    __tablename__ = 'streetview_organization'

    id = Column(Integer, primary_key=True)
    streetview_id = Column(ForeignKey('streetview.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    streetview = relationship('Streetview')
    key = Column(String())
    name = Column(String())
    slug = Column(String())

    def __repr__(self):
        return '<StreetviewOrganization(id={})>'.format(self.id)


class StreetviewInstance(Base):
    __tablename__ = 'streetview_instance'

    id = Column(Integer, primary_key=True)

    streetview_id = Column(ForeignKey('streetview.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    streetview = relationship('Streetview')
    system_id = Column(String(), nullable=True, index=True)
    path = Column(String(), nullable=True, index=True)
    sequences = relationship('StreetviewSequence', cascade="all, delete-orphan")

    def __repr__(self):
        return '<StreetviewInstance(id={})>'.format(self.id)


class StreetviewSequence(Base):
    __tablename__ = 'streetview_sequence'

    id = Column(Integer, primary_key=True)
    feature_id = Column(ForeignKey('features.id', ondelete="SET NULL", onupdate="CASCADE"), index=True)
    task_id = Column(ForeignKey('tasks.id'), index=True)
    sequence_id = Column(String(), index=True)
    organization_id = Column(String(), index=True)
    streetview_instance_id = Column(ForeignKey('streetview_instance.id', ondelete="CASCADE", onupdate="CASCADE"), index=True)
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    bbox = Column(String(), index=True)
    streetview_instance = relationship('StreetviewInstance')
    feature = relationship("Feature", lazy="joined")
    task = relationship("Task", lazy="joined")

    def __repr__(self):
        return '<StreetviewSequence(id={})>'.format(self.id)
