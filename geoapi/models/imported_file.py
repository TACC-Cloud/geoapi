from sqlalchemy.sql import func
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, Boolean, DateTime
)
from geoapi.db import Base

class ImportedFile(Base):
    __tablename__ = 'imported_file'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete="CASCADE"), index=True)
    system_id = Column(String, nullable=False, index=True)
    path = Column(String, nullable=False, index=True)
    # last_updated is the timestamp on the file itself as to when it was last touched
    last_updated = Column(DateTime(timezone=True), nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now())
    successful_import = Column(Boolean, default=True)

    def __repr__(self):
        return '<ImportedFile(system={sys}::path={path})>'.format(sys=self.system_id, path=self.path)
