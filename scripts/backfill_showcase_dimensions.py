"""
Backfill width and height columns for existing showcase_items in DB.

Usage:
  conda activate renderpop
  python -m scripts.backfill_showcase_dimensions
"""

from __future__ import annotations

import asyncio
import struct
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.db import dispose_engine, get_session_factory
from app.models.showcase import ShowcaseItem

_LOCAL_SOURCE = Path("/Users/zx/Desktop/image")
_IMAGE_EXTS = (".jpeg", ".jpg", ".png", ".webp")


def _sips_size(path: Path) -> tuple[int, int] | None:
    try:
        proc = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    w = h = None
    for line in proc.stdout.splitlines():
        if "pixelWidth" in line:
            w = int(line.split()[-1])
        if "pixelHeight" in line:
            h = int(line.split()[-1])
    if w and h:
        return w, h
    return None


def _get_image_size_from_bytes(data: bytes) -> tuple[int, int] | None:
    """Parse image dimensions from JPEG, PNG, or WebP byte streams using stdlib struct."""
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return w, h

    if data.startswith(b"\xff\xd8"):
        size = len(data)
        offset = 2
        while offset < size:
            if data[offset] != 0xFF:
                break
            marker = data[offset + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
                if offset + 9 <= size:
                    h, w = struct.unpack(">HH", data[offset + 5 : offset + 9])
                    return w, h
            length = struct.unpack(">H", data[offset + 2 : offset + 4])[0]
            offset += 2 + length

    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        chunk_type = data[12:16]
        if chunk_type == b"VP8 " and len(data) >= 30:
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        elif chunk_type == b"VP8L" and len(data) >= 25:
            b0, b1, b2, b3 = data[21:25]
            w = 1 + (((b1 & 0x3F) << 8) | b0)
            h = 1 + (((b3 & 0xF) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
            return w, h
        elif chunk_type == b"VP8X" and len(data) >= 30:
            w = 1 + struct.unpack("<I", data[24:27] + b"\x00")[0]
            h = 1 + struct.unpack("<I", data[27:30] + b"\x00")[0]
            return w, h

    return None


def _fetch_image_size(url: str) -> tuple[int, int] | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (RenderPop-Dimension-Fetcher)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            return _get_image_size_from_bytes(data)
    except Exception as exc:
        print(f"  [error] failed to fetch/parse image at {url}: {exc}")
        return None


def _get_size_for_item(sort_order: int, image_url: str) -> tuple[int, int] | None:
    # 1. Try local Desktop image folder
    if _LOCAL_SOURCE.is_dir():
        for ext in _IMAGE_EXTS:
            local_path = _LOCAL_SOURCE / f"{sort_order}{ext}"
            if local_path.is_file():
                size = _sips_size(local_path)
                if size:
                    return size

    # 2. Fall back to network fetch
    return _fetch_image_size(image_url)


async def main() -> None:
    factory = get_session_factory()
    updated_count = 0

    async with factory() as session:
        result = await session.execute(
            select(ShowcaseItem).where(ShowcaseItem.deleted_at.is_(None))
        )
        items = result.scalars().all()
        print(f"found {len(items)} active showcase items in database")

        for item in items:
            if item.width and item.height:
                print(f"#{item.sort_order} {item.title}: already has dimensions ({item.width}x{item.height})")
                continue

            print(f"#{item.sort_order} {item.title}: resolving dimensions...")
            size = _get_size_for_item(item.sort_order, item.image_url)
            if size:
                w, h = size
                item.width = w
                item.height = h
                updated_count += 1
                print(f"  -> set dimensions: {w}x{h}")
            else:
                print("  -> failed to parse dimensions")

        if updated_count > 0:
            await session.commit()
            print(f"\nsuccessfully backfilled {updated_count} item(s) in DB")
        else:
            print("\nno items needed update")

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
