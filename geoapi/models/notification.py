from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from geoapi.db import Base


class Notification(Base):

    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(256))
    message = Column(String(512))
    viewed = Column(Boolean, default=False)


class ProgressNotification(Base):

    __tablename__ = "progress_notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    tenant_id = Column(String)
    uuid = Column(UUID(as_uuid=True))
    username = Column(String, nullable=True, index=True)
    tenant_id = Column(String)
    created = Column(DateTime(timezone=True), server_default=func.now())
    progress = Column(Integer)
    status = Column(String(256))
    message = Column(String(512))
    logs = Column(JSONB, default={})
    viewed = Column(Boolean, default=False)
