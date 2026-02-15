from datetime import datetime
from decimal import Decimal

from typing import Optional
from sqlalchemy import String, ForeignKey, Numeric, MetaData, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.utils.time import now
from app.model.types.enums import RecordType, Currency

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


class SimpleIdMixin:
    """Simple auto-incrementing integer primary key mixin."""

    id: Mapped[int] = mapped_column(primary_key=True)


class AuditableMixin:
    """Simple mixin to add created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(default=lambda: now())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: now(), onupdate=lambda: now()
    )


# ### SITE MODELS ### #


class Domain(SimpleIdMixin, AuditableMixin, Base):
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True)

    sites: Mapped[list["Site"]] = relationship("Site", back_populates="domain")
    domain_regulations: Mapped[Optional["DomainRegulation"]] = relationship(
        "DomainRegulation", back_populates="domain"
    )


class Site(SimpleIdMixin, AuditableMixin, Base):
    __tablename__ = "sites"

    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id"))
    url: Mapped[str] = mapped_column(unique=True)

    domain: Mapped[Domain] = relationship("Domain", back_populates="sites")
    crawls: Mapped[list["Crawl"]] = relationship("Crawl", back_populates="site")


class DomainRegulation(SimpleIdMixin, AuditableMixin, Base):
    __tablename__ = "domain_regulations"

    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id"))
    is_allowed: Mapped[bool] = mapped_column()  # If domain is allowed for crawling

    domain: Mapped[Domain] = relationship("Domain", back_populates="regulations")


# ### CRAWL MODELS ### #


class Crawl(SimpleIdMixin, Base):
    __tablename__ = "crawls"

    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    started_at: Mapped[datetime] = mapped_column(default=lambda: now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(default=None)

    site: Mapped[Site] = relationship("Site")
    records: Mapped[list["Record"]] = relationship("Record", back_populates="crawl")


# ### INFO MODELS ### #


class Record(AuditableMixin, Base):
    """Base class for all records. It joins on other types of records"""

    # TODO: Do not forget to create record_type for each new record type!
    __tablename__ = "records"
    id: Mapped[int] = mapped_column(primary_key=True)

    crawl_id: Mapped[int] = mapped_column(ForeignKey("crawls.id"))
    record_type: Mapped[RecordType] = mapped_column(String(50))

    crawl: Mapped[Crawl] = relationship("Crawl")
    __mapper_args__ = {
        "polymorphic_identity": "record",
        "polymorphic_on": "record_type",
    }


class RealEstateRecord(Record):
    __tablename__ = "real_estate_records"

    id: Mapped[int] = mapped_column(ForeignKey("records.id"), primary_key=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    title: Mapped[str] = mapped_column(String(2048))
    price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=12, scale=2), default=None
    )
    currency: Mapped[Optional[Currency]] = mapped_column(String(3), default=None)
    location: Mapped[Optional[str]] = mapped_column(String(2048))

    descriptions = relationship("Description", back_populates="record")

    __table_args__ = (
        CheckConstraint("price >= 0", name="check_price_non_negative"),
        CheckConstraint(
            "(price IS NULL AND currency IS NULL) OR (price IS NOT NULL AND currency IS NOT NULL)",
            name="check_price_currency_together",
        ),
    )

    __mapper_args__ = {
        "polymorphic_identity": RecordType.REAL_ESTATE.value,
    }


class Description(SimpleIdMixin, AuditableMixin, Base):
    __tablename__ = "descriptions"

    record_id: Mapped[int] = mapped_column(ForeignKey("records.id"))
    current: Mapped[bool] = mapped_column(
        default=True
    )  # Keep a track of history of descriptions
    text: Mapped[str] = mapped_column(String(16384))

    record: Mapped[Record] = relationship("Record")
