"""Catalog of generation models (capabilities + pricing). Users do not pick models."""

from sqlalchemy import JSON, Boolean, Column, Integer, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TimestampedModel
from app.models.enums import (
    GenerationModelStatus,
    GenerationProvider,
    ModelModality,
    PricingType,
    sa_str_enum,
)


class GenerationModel(SoftDeleteMixin, TimestampedModel, table=True):
    """
    Server-side generation model row.

    C-end never lists provider or model marketplace — service routes by job_type
    to the default ACTIVE model for that modality/task.
    """

    __tablename__ = "generation_models"
    __table_args__ = (UniqueConstraint("code", name="uq_generation_models_code"),)

    code: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    name: str = Field(sa_column=Column(String(255), nullable=False))
    display_name: str = Field(sa_column=Column(String(255), nullable=False))
    modality: ModelModality = Field(
        sa_column=Column(sa_str_enum(ModelModality), nullable=False, index=True)
    )
    # e.g. ["TEXT_VIDEO", "IMAGE_VIDEO"]
    task_types: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    provider: GenerationProvider = Field(
        sa_column=Column(
            sa_str_enum(GenerationProvider, length=64),
            nullable=False,
            index=True,
        )
    )
    # Provider path/id: pollo-v2-0, RH app id, etc.
    provider_model_ref: str = Field(sa_column=Column(String(128), nullable=False))
    status: GenerationModelStatus = Field(
        default=GenerationModelStatus.DRAFT,
        sa_column=Column(
            sa_str_enum(GenerationModelStatus),
            nullable=False,
            server_default=GenerationModelStatus.DRAFT.value,
            index=True,
        ),
    )
    is_default: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="0", index=True),
    )
    sort_order: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )

    supported_lengths: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    supported_resolutions: list | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    supported_aspect_ratios: list | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    supports_audio: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="0"),
    )
    supports_image_input: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="0"),
    )
    supports_text_input: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="1"),
    )

    default_length: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    default_resolution: str | None = Field(
        default=None, sa_column=Column(String(16), nullable=True)
    )
    default_aspect_ratio: str | None = Field(
        default=None, sa_column=Column(String(16), nullable=True)
    )
    default_generate_audio: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="0"),
    )

    pricing_type: PricingType = Field(
        default=PricingType.FORMULA,
        sa_column=Column(
            sa_str_enum(PricingType),
            nullable=False,
            server_default=PricingType.FORMULA.value,
        ),
    )
    pricing_config: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    pricing_version: str = Field(
        default="1",
        sa_column=Column(String(32), nullable=False, server_default="1"),
    )
    estimated_wait_seconds: int = Field(
        default=60,
        sa_column=Column(Integer, nullable=False, server_default="60"),
    )
    config_version: str = Field(
        default="1",
        sa_column=Column(String(32), nullable=False, server_default="1"),
    )
