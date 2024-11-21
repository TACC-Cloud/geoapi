from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from geoapi.db import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    process_id = Column(String(), nullable=False)
    status = Column(String())
    description = Column(String())
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return (
            f"<Task(id={self.id} process_id={self.process_id} status={self.status} "
            f"description={self.description} updated={self.updated} )>"
        )
