from sqlalchemy import Boolean, String, DateTime
from sqlalchemy.orm import mapped_column


class FileLocationTrackingMixin:
    """
    Mixin for tracking file locations (original and current) and public accessibility.

    Tracks:
    - Original location: where the file was first sourced from
    - Current location: where the file is now (may differ if published/moved)
    - Public accessibility: whether current location is publicly accessible
    - Last check timestamp: when accessibility was last verified
    - DesignSafe project id, e.g. 'PRJ-1234', associated with the system
    """
    original_system = mapped_column(
        String(),
        nullable=True,
        index=True,
        comment="Tapis system where the original file was sourced from",
    )
    original_path = mapped_column(
        String(),
        nullable=True,
        index=True,  # Adding index for TileServer too
        comment="Original file path on the source system",
    )
    current_path = mapped_column(
        String(),
        nullable=True,
        index=True,
        comment="Current file path (updated if file is published or moved)",
    )
    current_system = mapped_column(
        String(),
        nullable=True,
        index=True,
        comment="Current Tapis system (updated if file is published or moved)",
    )
    designsafe_project_id = mapped_column(
        String(),
        nullable=True,
        index=True,
        comment="DesignSafe project ID, e.g. 'PRJ-1234', associated with current_system/original_system",
    )
    is_on_public_system = mapped_column(
        Boolean(),
        nullable=True,
        comment="Whether the current_system is publicly accessible",
    )
    last_public_system_check = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last public accessibility check",
    )
