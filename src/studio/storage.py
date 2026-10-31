from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "source_items"
    __table_args__ = (UniqueConstraint("platform", "content_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(20))
    content_id: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="DISCOVERED")
    transcript: Mapped[str | None] = mapped_column(Text)
    transcript_provenance: Mapped[str | None] = mapped_column(Text)
    research: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)


class Audit(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("source_items.id"))
    actor: Mapped[str] = mapped_column(String(100))
    previous: Mapped[str] = mapped_column(String(30))
    current: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Report(Base):
    __tablename__ = "daily_reports"
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="prepared")


def database(url: str):
    engine = create_engine(url)
    return engine, sessionmaker(engine, expire_on_commit=False)
