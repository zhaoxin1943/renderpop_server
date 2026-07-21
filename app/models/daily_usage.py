from datetime import date

from sqlalchemy import Column, Date, Integer, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import TimestampedModel
from app.models.enums import UsageFeature, UsageSubjectType, sa_str_enum


class DailyUsageCounter(TimestampedModel, table=True):
    """Atomic daily quota counters (e.g. FAST_IMAGE)."""

    __tablename__ = "daily_usage_counters"
    __table_args__ = (
        UniqueConstraint(
            "subject_type",
            "subject_id",
            "feature",
            "usage_date",
            name="uq_daily_usage_subject_feature_date",
        ),
    )

    subject_type: UsageSubjectType = Field(
        sa_column=Column(sa_str_enum(UsageSubjectType), nullable=False)
    )
    subject_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    feature: UsageFeature = Field(
        sa_column=Column(sa_str_enum(UsageFeature, length=64), nullable=False, index=True)
    )
    usage_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    used_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    limit_snapshot: int = Field(sa_column=Column(Integer, nullable=False))
