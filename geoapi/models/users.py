import pytz
from datetime import datetime, timedelta
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, mapped_column
from geoapi.db import Base
from geoapi.utils import jwt_utils


class User(Base):
    __tablename__ = "users"
    id = mapped_column(Integer, primary_key=True)
    username = mapped_column(String, unique=True, index=True)
    tenant_id = mapped_column(String, nullable=False)
    created = mapped_column(DateTime(timezone=True), server_default=func.now())
    auth = relationship("Auth", uselist=False, cascade="all, delete-orphan")
    streetviews = relationship("Streetview", cascade="all, delete-orphan")
    projects = relationship(
        "Project",
        secondary="projects_users",
        back_populates="users",
        lazy="select",
        overlaps="project,project_users",
    )
    project_users = relationship("ProjectUser", back_populates="user")

    def __repr__(self):
        access_token_masked = None
        refresh_token_masked = None

        if self.auth:
            access_token_masked = (
                self.auth.access_token[-5:] if self.auth.access_token else None
            )
            refresh_token_masked = (
                self.auth.refresh_token[-5:] if self.auth.refresh_token else None
            )

        return (
            f"<User(uname={self.username}, "
            f"id={self.id},"
            f"tenant={self.tenant_id})"
            f"access_token={access_token_masked},"
            f"access_token_expires_at={self.auth.access_token_expires_at},"
            f"refresh_token={refresh_token_masked},"
            f"refresh_token_expires_at={self.auth.refresh_token_expires_at})> "
        )

    @hybrid_property
    def jwt(self):
        """Get access token from auth"""
        return self.auth.access_token

    def has_unexpired_refresh_token(self) -> bool:
        """
        Check if refresh token is expired with a 1-minute buffer.

        Returns:
            bool: True if the refresh token is expired (or doesn't exist), False otherwise.
        """
        if not self.auth or not self.auth.refresh_token:
            return False
        current_time = datetime.now(pytz.utc)  # Make current_time offset-aware with UTC
        buffer = timedelta(minutes=1)  # 1 minute buffer
        return current_time <= (self.auth.refresh_token_expires_at - buffer)

    def has_valid_token(self) -> bool:
        """Check if access_token is valid"""
        return (
            self.auth
            and self.auth.access_token
            and jwt_utils.is_token_valid(self.auth.access_token)
        )
