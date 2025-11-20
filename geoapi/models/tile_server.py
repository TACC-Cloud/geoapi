from sqlalchemy import Boolean, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, UUID
from geoapi.db import Base
from geoapi.models.file_location_tracking_mixin import FileLocationTrackingMixin


class TileServer(Base, FileLocationTrackingMixin):
    __tablename__ = "tile_servers"
    id = mapped_column(Integer, primary_key=True)
    project_id = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE", onupdate="CASCADE"), index=True
    )
    name = mapped_column(String(), nullable=False)
    type = mapped_column(String(), nullable=False)
    kind = mapped_column(
        String(), nullable=True, comment=("Source kind for what the data is (e.g. cog)")
    )

    internal = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment=(
            "True when served internally by our stack (e.g., TiTiler). "
            "When true, 'uuid' must be non-null. External layers keep this false."
        ),
    )

    uuid = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment=(
            "Identifier for internally managed assets (e.g., the generated COG file).  "
            "Required when 'internal' is true; null for external layers."
        ),
    )

    url = mapped_column(
        String(),
        nullable=False,
        comment=(
            "For internal=true: file path to asset (e.g., /assets/3/uuid.cog.tif)."
            "For internal=false: full tile URL template with {z}/{x}/{y} placeholders."
        ),
    )

    attribution = mapped_column(String(), nullable=False)

    # Note: original_system, original_path, current_system, current_path,
    #       is_on_public_system, and last_public_system_check are inherited
    #       from FileLocationTrackingMixin

    tileOptions = mapped_column(JSONB, default={})
    uiOptions = mapped_column(JSONB, default={})

    project = relationship("Project")

    def __repr__(self):
        return "<TileServer(id={})>".format(self.id)
