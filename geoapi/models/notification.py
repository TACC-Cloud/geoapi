import uuid
from sqlalchemy import (
    Column, Integer, String,
    Boolean, DateTime
)
from sqlalchemy.sql import func
from geoapi.db import Base


class Notification(Base):

    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(256))
    message = Column(String(512))
    viewed = Column(Boolean, default=False)
