"""SQLAlchemy models for the Precious Metals Liquidity Monitor."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class ComponentType(str, enum.Enum):
    """Component types for liquidity metrics."""

    INVENTORY = "inventory"
    ETF_FLOW = "etf_flow"
    TERM = "term"
    COT = "cot"
    PREMIUM = "premium"
    FX = "fx"


class FrequencyType(str, enum.Enum):
    """Data frequency types."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ETLStatus(str, enum.Enum):
    """ETL run status."""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class Metal(Base):
    """Precious metals being tracked."""

    __tablename__ = "metals"

    metal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    series: Mapped[list["Series"]] = relationship(back_populates="metal", cascade="all, delete")
    scores: Mapped[list["Score"]] = relationship(back_populates="metal", cascade="all, delete")
    composites: Mapped[list["Composite"]] = relationship(
        back_populates="metal", cascade="all, delete"
    )


class Source(Base):
    """Data sources."""

    __tablename__ = "sources"

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    series: Mapped[list["Series"]] = relationship(back_populates="source")
    etl_runs: Mapped[list["ETLRun"]] = relationship(back_populates="source")


class Series(Base):
    """Time series definitions."""

    __tablename__ = "series"

    series_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metal_id: Mapped[int] = mapped_column(ForeignKey("metals.metal_id"), nullable=False)
    component: Mapped[ComponentType] = mapped_column(Enum(ComponentType), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    freq: Mapped[FrequencyType] = mapped_column(Enum(FrequencyType), nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.source_id"), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    metal: Mapped["Metal"] = relationship(back_populates="series")
    source: Mapped["Source"] = relationship(back_populates="series")
    observations: Mapped[list["Observation"]] = relationship(
        back_populates="series", cascade="all, delete"
    )

    __table_args__ = (Index("ix_series_metal_component", "metal_id", "component"),)


class Observation(Base):
    """Raw time series observations."""

    __tablename__ = "observations"

    series_id: Mapped[int] = mapped_column(
        ForeignKey("series.series_id"), primary_key=True, nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True, nullable=False)
    v: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source_revision_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    series: Mapped["Series"] = relationship(back_populates="observations")

    __table_args__ = (
        Index("ix_observations_series_ts", "series_id", "ts"),
        Index("ix_observations_ts", "ts"),
    )


class FormulaVersion(Base):
    """Formula versions for scoring."""

    __tablename__ = "formula_versions"

    formula_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    weights: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    scores: Mapped[list["Score"]] = relationship(back_populates="formula")
    composites: Mapped[list["Composite"]] = relationship(back_populates="formula")


class Score(Base):
    """Component scores."""

    __tablename__ = "scores"

    metal_id: Mapped[int] = mapped_column(
        ForeignKey("metals.metal_id"), primary_key=True, nullable=False
    )
    component: Mapped[ComponentType] = mapped_column(
        Enum(ComponentType), primary_key=True, nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True, nullable=False)
    s: Mapped[int] = mapped_column(
        SmallInteger, CheckConstraint("s >= 0 AND s <= 100"), nullable=False
    )
    v: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    window: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    formula_id: Mapped[int] = mapped_column(ForeignKey("formula_versions.formula_id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    metal: Mapped["Metal"] = relationship(back_populates="scores")
    formula: Mapped["FormulaVersion"] = relationship(back_populates="scores")

    __table_args__ = (
        Index("ix_scores_metal_ts", "metal_id", "ts"),
        Index("ix_scores_ts", "ts"),
    )


class Composite(Base):
    """Composite liquidity indices."""

    __tablename__ = "composites"

    metal_id: Mapped[int] = mapped_column(
        ForeignKey("metals.metal_id"), primary_key=True, nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True, nullable=False)
    s: Mapped[int] = mapped_column(
        SmallInteger, CheckConstraint("s >= 0 AND s <= 100"), nullable=False
    )
    components: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    formula_id: Mapped[int] = mapped_column(ForeignKey("formula_versions.formula_id"))
    degraded: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    metal: Mapped["Metal"] = relationship(back_populates="composites")
    formula: Mapped["FormulaVersion"] = relationship(back_populates="composites")

    __table_args__ = (
        Index("ix_composites_metal_ts", "metal_id", "ts"),
        Index("ix_composites_ts", "ts"),
    )


class ETLRun(Base):
    """ETL execution tracking."""

    __tablename__ = "etl_runs"

    etl_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.source_id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[ETLStatus] = mapped_column(Enum(ETLStatus), nullable=False)
    rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships
    source: Mapped["Source"] = relationship(back_populates="etl_runs")

    __table_args__ = (Index("ix_etl_runs_source_started", "source_id", "started_at"),)


class RedditConfig(Base):
    """Per-subreddit Reddit bot configuration."""

    __tablename__ = "reddit_configs"

    config_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subreddit: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    metals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    post_hour: Mapped[int] = mapped_column(
        Integer, CheckConstraint("post_hour >= 0 AND post_hour < 24"), default=12
    )
    verbosity: Mapped[str] = mapped_column(String(20), default="normal")
    alert_thresholds: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
