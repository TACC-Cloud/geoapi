from sqlalchemy import Integer, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from geoapi.db import Base
from sqlalchemy.orm import mapped_column


class Notification(Base):

    __tablename__ = "notifications"
    id = mapped_column(Integer, primary_key=True)
    username = mapped_column(String, nullable=False, index=True)
    tenant_id = mapped_column(String, nullable=False)
    created = mapped_column(DateTime(timezone=True), server_default=func.now())
    status = mapped_column(String(256))
    message = mapped_column(String(512))
    viewed = mapped_column(Boolean, default=False)


class ProgressNotification(Base):

    __tablename__ = "progress_notifications"
    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(Integer)
    uuid = mapped_column(UUID(as_uuid=True))
    username = mapped_column(String, nullable=True, index=True)
    tenant_id = mapped_column(String)
    created = mapped_column(DateTime(timezone=True), server_default=func.now())
    progress = mapped_column(Integer)
    status = mapped_column(String(256))
    message = mapped_column(String(512))
    logs = mapped_column(JSONB, default={})
    viewed = mapped_column(Boolean, default=False)
