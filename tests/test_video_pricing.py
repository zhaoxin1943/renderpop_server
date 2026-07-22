"""Unit tests for AI video credit formula (BASE=15, audio ×4) and image pricing helpers."""

from app.core.commerce import (
    PRO_IMAGE_CREDITS,
    default_rh_fixed_pricing_config,
    default_rh_quota_pricing_config,
    default_video_pricing_config,
    image_credits_from_pricing_config,
    pricing_requires_login,
    pricing_uses_fast_daily_quota,
    video_credits,
    video_credits_from_pricing_config,
)


def test_video_credits_matrix() -> None:
    assert video_credits(length=5, resolution="480p") == 15
    assert video_credits(length=5, resolution="720p") == 30
    assert video_credits(length=5, resolution="1080p") == 60
    assert video_credits(length=10, resolution="480p") == 30
    assert video_credits(length=10, resolution="720p") == 60
    assert video_credits(length=10, resolution="1080p") == 120


def test_video_credits_with_audio() -> None:
    assert video_credits(length=5, resolution="480p", generate_audio=True) == 60
    assert video_credits(length=5, resolution="720p", generate_audio=True) == 120
    assert video_credits(length=5, resolution="1080p", generate_audio=True) == 240
    assert video_credits(length=10, resolution="480p", generate_audio=True) == 120
    assert video_credits(length=10, resolution="720p", generate_audio=True) == 240
    assert video_credits(length=10, resolution="1080p", generate_audio=True) == 480


def test_pricing_config_formula() -> None:
    cfg = default_video_pricing_config()
    assert (
        video_credits_from_pricing_config(cfg, length=5, resolution="720p") == 30
    )
    assert (
        video_credits_from_pricing_config(
            cfg, length=10, resolution="1080p", generate_audio=False
        )
        == 120
    )
    assert (
        video_credits_from_pricing_config(
            cfg, length=5, resolution="720p", generate_audio=True
        )
        == 120
    )
    assert (
        video_credits_from_pricing_config(
            cfg, length=10, resolution="1080p", generate_audio=True
        )
        == 480
    )


def test_pricing_config_lookup() -> None:
    cfg = {
        "type": "lookup",
        "table": {
            "5|720p|false": 30,
            "5|720p|true": 120,
            "10|1080p|false": 120,
        },
    }
    assert (
        video_credits_from_pricing_config(cfg, length=5, resolution="720p") == 30
    )
    assert (
        video_credits_from_pricing_config(
            cfg, length=5, resolution="720p", generate_audio=True
        )
        == 120
    )


def test_pollo_unwrap_envelope() -> None:
    from app.providers.pollo import PolloClient

    flat = {"taskId": "abc", "status": "waiting"}
    assert PolloClient._unwrap(flat)["taskId"] == "abc"

    env = {
        "code": "SUCCESS",
        "message": "success",
        "data": {"taskId": "xyz", "status": "waiting"},
    }
    out = PolloClient._unwrap(env)
    assert out["taskId"] == "xyz"
    assert out["status"] == "waiting"
    assert out["_envelope_code"] == "SUCCESS"


def test_rh_image_pricing_helpers() -> None:
    quota = default_rh_quota_pricing_config(
        requires_login=False, pricing_version="image-fast"
    )
    fixed = default_rh_fixed_pricing_config(credits=PRO_IMAGE_CREDITS)
    assert image_credits_from_pricing_config(quota) == 0
    assert image_credits_from_pricing_config(fixed) == PRO_IMAGE_CREDITS
    assert pricing_uses_fast_daily_quota(quota) is True
    assert pricing_uses_fast_daily_quota(fixed) is False
    assert pricing_requires_login(quota, default=True) is False
    assert pricing_requires_login(fixed, default=False) is True
