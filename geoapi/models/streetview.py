from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship, mapped_column
from geoapi.db import Base


class Streetview(Base):
    """
    Represents a user's access to a streetview-related service (e.g., Mapillary).

    This model stores user credentials, service information, and associated organizations
    and instances of streetview data. Each `Streetview` entry is tied to a specific user
    and contains authentication details required for interacting with the streetview service.
    """

    __tablename__ = "streetview"

    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), index=True
    )
    user = relationship("User", overlaps="streetviews")
    token = mapped_column(String())
    token_expires_at = mapped_column(DateTime(timezone=True))
    service = mapped_column(String())
    service_user = mapped_column(String())
    organizations = relationship("StreetviewOrganization", cascade="all, delete-orphan")
    instances = relationship("StreetviewInstance", cascade="all, delete-orphan")

    def __repr__(self):
        token_masked = self.token[-5:] if self.token else None
        return (
            f"<Streetview(id={self.id}, user:{self.user.username},"
            f"service:{self.service}, service_user:{self.service_user}),"
            f"token:{token_masked}, token_expires_at:{self.token_expires_at}>"
        )


class StreetviewOrganization(Base):
    __tablename__ = "streetview_organization"

    id = mapped_column(Integer, primary_key=True)
    streetview_id = mapped_column(
        ForeignKey("streetview.id", ondelete="CASCADE", onupdate="CASCADE"), index=True
    )
    streetview = relationship("Streetview", overlaps="organizations")
    key = mapped_column(String())
    name = mapped_column(String())
    slug = mapped_column(String())

    def __repr__(self):
        return "<StreetviewOrganization(id={})>".format(self.id)


class StreetviewInstance(Base):
    __tablename__ = "streetview_instance"

    id = mapped_column(Integer, primary_key=True)

    streetview_id = mapped_column(
        ForeignKey("streetview.id", ondelete="CASCADE", onupdate="CASCADE"), index=True
    )
    streetview = relationship("Streetview", overlaps="instances")
    system_id = mapped_column(String(), nullable=True, index=True)
    path = mapped_column(String(), nullable=True, index=True)
    sequences = relationship("StreetviewSequence", cascade="all, delete-orphan")

    def __repr__(self):
        return "<StreetviewInstance(id={})>".format(self.id)


class StreetviewSequence(Base):
    __tablename__ = "streetview_sequence"

    id = mapped_column(Integer, primary_key=True)
    feature_id = mapped_column(
        ForeignKey("features.id", ondelete="SET NULL", onupdate="CASCADE"), index=True
    )
    task_id = mapped_column(ForeignKey("tasks.id"), index=True)
    sequence_id = mapped_column(String(), index=True)
    organization_id = mapped_column(String(), index=True)
    streetview_instance_id = mapped_column(
        ForeignKey("streetview_instance.id", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )
    start_date = mapped_column(DateTime(timezone=True))
    end_date = mapped_column(DateTime(timezone=True))
    bbox = mapped_column(String(), index=True)
    streetview_instance = relationship("StreetviewInstance", overlaps="sequences")
    feature = relationship("Feature", lazy="joined")
    task = relationship("Task", lazy="joined")

    def __repr__(self):
        return "<StreetviewSequence(id={})>".format(self.id)
