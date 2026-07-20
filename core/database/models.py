"""
All SQLAlchemy ORM models for Aurum Commerce OS.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer,
    JSON, String, Text, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from .base import Base, TimestampMixin, UUIDMixin


# ── Enums ─────────────────────────────────────────────────────────────────────

class ProductLifecycle(str, enum.Enum):
    NEW_TREND    = "new_trend"
    FAST_GROWTH  = "fast_growth"
    MATURE       = "mature"
    SEASONAL     = "seasonal"
    EVERGREEN    = "evergreen"
    DECLINING    = "declining"


class ProductStatus(str, enum.Enum):
    DISCOVERED   = "discovered"
    EVALUATING   = "evaluating"
    APPROVED     = "approved"
    REJECTED     = "rejected"
    LAUNCHED     = "launched"
    SCALING      = "scaling"
    MAINTAINING  = "maintaining"
    RETIRING     = "retiring"
    RETIRED      = "retired"


class ApprovalStatus(str, enum.Enum):
    PENDING    = "pending"
    APPROVED   = "approved"
    REJECTED   = "rejected"
    EXPIRED    = "expired"


class AgentStatus(str, enum.Enum):
    IDLE       = "idle"
    RUNNING    = "running"
    SUCCESS    = "success"
    FAILED     = "failed"
    PAUSED     = "paused"


class StoreStatus(str, enum.Enum):
    ACTIVE     = "active"
    INACTIVE   = "inactive"
    SUSPENDED  = "suspended"


class AlertSeverity(str, enum.Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


class CampaignStatus(str, enum.Enum):
    DRAFT             = "draft"             # built, not yet submitted for approval
    PENDING_APPROVAL  = "pending_approval"   # awaiting human sign-off (all ad spend requires this)
    ACTIVE            = "active"             # live on the ad platform
    PAUSED            = "paused"
    REJECTED          = "rejected"
    ENDED             = "ended"
    FAILED            = "failed"             # platform API rejected it / error creating it


# ── Store ─────────────────────────────────────────────────────────────────────

class Store(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stores"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    niche: Mapped[Optional[str]] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(50), default="shopify")
    domain: Mapped[Optional[str]] = mapped_column(String(300))
    shopify_store_url: Mapped[Optional[str]] = mapped_column(String(300))
    status: Mapped[StoreStatus] = mapped_column(
        SAEnum(StoreStatus), default=StoreStatus.ACTIVE
    )
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    products: Mapped[list["Product"]] = relationship(back_populates="store")
    metrics: Mapped[list["StoreMetric"]] = relationship(back_populates="store")


# ── Product ───────────────────────────────────────────────────────────────────

class Product(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "products"

    store_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), nullable=True
    )
    shopify_product_id: Mapped[Optional[str]] = mapped_column(String(50))

    # Identity
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(200))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    image_url: Mapped[Optional[str]] = mapped_column(String(1000))
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    source_platform: Mapped[Optional[str]] = mapped_column(String(100))

    # Scoring
    opportunity_score: Mapped[Optional[float]] = mapped_column(Float)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    risk_score: Mapped[Optional[float]] = mapped_column(Float)
    demand_score: Mapped[Optional[float]] = mapped_column(Float)
    competition_score: Mapped[Optional[float]] = mapped_column(Float)

    # Financials
    supplier_cost: Mapped[Optional[float]] = mapped_column(Float)
    shipping_cost: Mapped[Optional[float]] = mapped_column(Float)
    selling_price: Mapped[Optional[float]] = mapped_column(Float)
    gross_margin: Mapped[Optional[float]] = mapped_column(Float)

    # Lifecycle
    lifecycle: Mapped[Optional[ProductLifecycle]] = mapped_column(
        SAEnum(ProductLifecycle)
    )
    status: Mapped[ProductStatus] = mapped_column(
        SAEnum(ProductStatus), default=ProductStatus.DISCOVERED
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Supplier
    supplier_name: Mapped[Optional[str]] = mapped_column(String(200))
    supplier_url: Mapped[Optional[str]] = mapped_column(String(1000))
    supplier_rating: Mapped[Optional[float]] = mapped_column(Float)
    shipping_days: Mapped[Optional[int]] = mapped_column(Integer)

    # Evidence
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)

    store: Mapped[Optional["Store"]] = relationship(back_populates="products")
    experiments: Mapped[list["Experiment"]] = relationship(back_populates="product")
    approvals: Mapped[list["ApprovalRequest"]] = relationship(back_populates="product")
    ad_campaigns: Mapped[list["AdCampaign"]] = relationship(back_populates="product")

    __table_args__ = (
        Index("ix_products_status", "status"),
        Index("ix_products_opportunity_score", "opportunity_score"),
        Index("ix_products_lifecycle", "lifecycle"),
        Index("ix_products_store_id", "store_id"),
    )


# ── Supplier ──────────────────────────────────────────────────────────────────

class Supplier(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(100))
    url: Mapped[Optional[str]] = mapped_column(String(1000))
    rating: Mapped[Optional[float]] = mapped_column(Float)
    avg_shipping_days: Mapped[Optional[float]] = mapped_column(Float)
    refund_rate: Mapped[Optional[float]] = mapped_column(Float)
    reliability_score: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


# ── Experiment ────────────────────────────────────────────────────────────────

class Experiment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "experiments"

    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )
    store_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    experiment_type: Mapped[str] = mapped_column(String(100))  # price, creative, bundle, etc.
    hypothesis: Mapped[Optional[str]] = mapped_column(Text)
    variants: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[dict] = mapped_column(JSON, default=dict)
    winner: Mapped[Optional[str]] = mapped_column(String(100))
    lift: Mapped[Optional[float]] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    product: Mapped[Optional["Product"]] = relationship(back_populates="experiments")


# ── Agent Run ──────────────────────────────────────────────────────────────────

class AgentRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_runs"

    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    task: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[AgentStatus] = mapped_column(
        SAEnum(AgentStatus), default=AgentStatus.IDLE
    )
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_agent_runs_agent_name", "agent_name"),
        Index("ix_agent_runs_status", "status"),
    )


# ── Approval Request ──────────────────────────────────────────────────────────

class ApprovalRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "approval_requests"

    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_campaigns.id"), nullable=True
    )
    request_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    impact: Mapped[Optional[str]] = mapped_column(Text)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    risk_assessment: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(200))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    product: Mapped[Optional["Product"]] = relationship(back_populates="approvals")
    campaign: Mapped[Optional["AdCampaign"]] = relationship()

    __table_args__ = (
        Index("ix_approval_requests_status", "status"),
    )


# ── Store Metric ──────────────────────────────────────────────────────────────

class StoreMetric(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "store_metrics"

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period: Mapped[str] = mapped_column(String(20), default="daily")

    # Revenue
    revenue: Mapped[Optional[float]] = mapped_column(Float)
    gross_profit: Mapped[Optional[float]] = mapped_column(Float)
    net_profit: Mapped[Optional[float]] = mapped_column(Float)
    gross_margin: Mapped[Optional[float]] = mapped_column(Float)

    # Orders
    orders: Mapped[Optional[int]] = mapped_column(Integer)
    aov: Mapped[Optional[float]] = mapped_column(Float)
    refund_rate: Mapped[Optional[float]] = mapped_column(Float)

    # Customers
    new_customers: Mapped[Optional[int]] = mapped_column(Integer)
    returning_customers: Mapped[Optional[int]] = mapped_column(Integer)
    clv: Mapped[Optional[float]] = mapped_column(Float)
    cac: Mapped[Optional[float]] = mapped_column(Float)

    # Marketing
    ad_spend: Mapped[Optional[float]] = mapped_column(Float)
    roas: Mapped[Optional[float]] = mapped_column(Float)
    conversion_rate: Mapped[Optional[float]] = mapped_column(Float)

    store: Mapped["Store"] = relationship(back_populates="metrics")

    __table_args__ = (
        Index("ix_store_metrics_store_date", "store_id", "date"),
    )


# ── Risk Alert ────────────────────────────────────────────────────────────────

class RiskAlert(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "risk_alerts"

    store_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), nullable=True
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        SAEnum(AlertSeverity), default=AlertSeverity.INFO
    )
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_risk_alerts_severity", "severity"),
        Index("ix_risk_alerts_resolved", "is_resolved"),
    )


# ── Executive Brief ───────────────────────────────────────────────────────────

class ExecutiveBrief(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "executive_briefs"

    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[dict] = mapped_column(JSON, default=dict)
    products_to_launch: Mapped[list] = mapped_column(JSON, default=list)
    products_to_retire: Mapped[list] = mapped_column(JSON, default=list)
    revenue_projection: Mapped[Optional[float]] = mapped_column(Float)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)


# ── Business Memory Entry ─────────────────────────────────────────────────────

class MemoryEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "memory_entries"

    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    source_agent: Mapped[Optional[str]] = mapped_column(String(100))
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)
    chroma_id: Mapped[Optional[str]] = mapped_column(String(200))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("ix_memory_entries_type", "memory_type"),
    )


# ── Competitor ────────────────────────────────────────────────────────────────

class Competitor(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "competitors"

    store_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1000))
    niche: Mapped[Optional[str]] = mapped_column(String(200))
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    changes: Mapped[list] = mapped_column(JSON, default=list)


# ── Trend Signal ──────────────────────────────────────────────────────────────

class TrendSignal(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "trend_signals"

    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    platform: Mapped[str] = mapped_column(String(100), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(100))
    strength: Mapped[Optional[float]] = mapped_column(Float)
    velocity: Mapped[Optional[float]] = mapped_column(Float)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_trend_signals_keyword", "keyword"),
        Index("ix_trend_signals_platform", "platform"),
    )


# ── Ad Campaign ───────────────────────────────────────────────────────────────

class AdCampaign(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ad_campaigns"

    store_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), nullable=True
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )
    product: Mapped[Optional["Product"]] = relationship(back_populates="ad_campaigns")

    platform: Mapped[str] = mapped_column(String(50), default="meta")
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    objective: Mapped[str] = mapped_column(String(100), default="OUTCOME_SALES")
    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(CampaignStatus), default=CampaignStatus.DRAFT
    )

    daily_budget: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="USD")

    # Ad copy + audience, generated before approval so a human reviews
    # exactly what will run, not just a budget number.
    creative: Mapped[dict] = mapped_column(JSON, default=dict)
    targeting: Mapped[dict] = mapped_column(JSON, default=dict)

    # External IDs once actually created on the platform
    platform_campaign_id: Mapped[Optional[str]] = mapped_column(String(100))
    platform_adset_id: Mapped[Optional[str]] = mapped_column(String(100))
    platform_ad_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Performance, refreshed periodically once live
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("ix_ad_campaigns_status", "status"),
        Index("ix_ad_campaigns_product_id", "product_id"),
    )
