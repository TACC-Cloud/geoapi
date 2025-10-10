from sqlalchemy.sql import func
from sqlalchemy import Integer, String, ForeignKey, Boolean, DateTime
from geoapi.db import Base
from sqlalchemy.orm import mapped_column


class ImportedFile(Base):
    __tablename__ = "imported_file"

    id = mapped_column(Integer, primary_key=True)
    project_id = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    system_id = mapped_column(String, nullable=False, index=True)
    path = mapped_column(String, nullable=False, index=True)
    # last_updated is the timestamp on the file itself as to when it was last touched
    last_updated = mapped_column(DateTime(timezone=True), nullable=False)
    created = mapped_column(DateTime(timezone=True), server_default=func.now())
    successful_import = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self):
        return "<ImportedFile(system={sys}::path={path})>".format(
            sys=self.system_id, path=self.path
        )
