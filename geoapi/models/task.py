from sqlalchemy import Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import mapped_column
from litestar.dto import dto_field
from geoapi.db import Base


class Task(Base):
    __tablename__ = "tasks"

    id = mapped_column(Integer, primary_key=True)
    process_id = mapped_column(String(), nullable=False, info=dto_field("private"))
    status = mapped_column(String())
    description = mapped_column(String())
    created = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated = mapped_column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return (
            f"<Task(id={self.id} process_id={self.process_id} status={self.status} "
            f"description={self.description} updated={self.updated} )>"
        )
