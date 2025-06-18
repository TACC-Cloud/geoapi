from sqlalchemy import Integer, String, DateTime, ForeignKey
from geoapi.db import Base
from sqlalchemy.orm import mapped_column


class Auth(Base):
    __tablename__ = "auth"
    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    access_token = mapped_column(String(2048))  # Tapis access token
    access_token_expires_at = mapped_column(DateTime(timezone=True))
    refresh_token = mapped_column(String(2048))  # Tapis refresh token
    refresh_token_expires_at = mapped_column(DateTime(timezone=True))

    def __repr__(self):
        access_token_masked = self.access_token[-5:] if self.access_token else None
        refresh_token_masked = self.refresh_token[-5:] if self.refresh_token else None
        return (
            f"<Auth(user_id={self.user_id}, "
            f"access_token={access_token_masked},"
            f"access_token_expires_at={self.access_token_expires_at},"
            f"refresh_token={refresh_token_masked},"
            f"refresh_token_expires_at={self.refresh_token_expires_at})> "
        )
