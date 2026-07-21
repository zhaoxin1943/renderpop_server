"""
Upload local waterfall assets to S3 (public media/showcase/*) and upsert DB rows.

Default source folder:
  /Users/zx/Desktop/image
  - N.jpeg|png  +  N.txt (prompt; English preferred)

Usage:
  conda activate renderpop
  python -m scripts.seed_showcase
  python -m scripts.seed_showcase --source /path/to/images
"""

from __future__ import annotations

import argparse
import asyncio
import mimetypes
import sys
from math import gcd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import dispose_engine, get_session_factory
from app.models.base import new_id, utc_now
from app.models.showcase import ShowcaseItem
from app.providers.s3 import S3Storage, get_s3_storage

# Hand-written English titles derived from each prompt's subject.
_TITLES: dict[int, str] = {
    1: "Fashion Week Walk Portrait",
    2: "Luxury Sedan Side Profile",
    3: "Cafe Window Dessert Smile",
    4: "Morning Looking Up Fashion",
    5: "Luxury Hotel Identity Portrait",
    6: "Vintage Bus Bench Portrait",
    7: "Soft Japanese Selfie Close-up",
    8: "Quiet Japanese Bar Moment",
    9: "Apricot Polo Mermaid Skirt",
    10: "Desert Golden Hour Swim",
    11: "High Bun Open-Back Dress",
    12: "Forest Crouch Bikini Portrait",
    13: "Peak Hour Commute Gaze",
    14: "Minimal Mirror Selfie",
    15: "Hotel Suite Soft Portrait",
    16: "Concrete Stairs Street Fashion",
    17: "Gaze Lingering on the Lips",
}

_IMAGE_EXTS = (".jpeg", ".jpg", ".png", ".webp")


def _find_image(source: Path, n: int) -> Path | None:
    for ext in _IMAGE_EXTS:
        path = source / f"{n}{ext}"
        if path.is_file():
            return path
    return None


def _load_prompt(n: int, source: Path) -> str:
    raw_path = source / f"{n}.txt"
    if not raw_path.is_file():
        raise FileNotFoundError(f"missing prompt file: {raw_path}")
    return raw_path.read_text(encoding="utf-8").strip()


def _image_size(path: Path) -> tuple[int, int] | None:
    """Read width/height via macOS sips; returns None if unavailable."""
    import subprocess

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


def _aspect_ratio(width: int | None, height: int | None) -> str:
    if not width or not height:
        return "9:16"
    ratio = width / height
    candidates = {
        "9:16": 9 / 16,
        "3:4": 3 / 4,
        "2:3": 2 / 3,
        "4:5": 4 / 5,
        "1:1": 1.0,
        "16:9": 16 / 9,
        "4:3": 4 / 3,
    }
    best = min(candidates, key=lambda k: abs(ratio - candidates[k]))
    if abs(ratio - candidates[best]) <= 0.04:
        return best
    g = gcd(width, height)
    return f"{width // g}:{height // g}"


def _content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    ext = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")


def _title_for(n: int, prompt: str) -> str:
    if n in _TITLES:
        return _TITLES[n]
    # Fallback: first ~6 content words from prompt.
    words = re.findall(r"[A-Za-z0-9']+", prompt)
    return " ".join(words[:6]).title() or f"Showcase {n}"


def collect_items(source: Path) -> list[dict]:
    items: list[dict] = []
    for n in range(1, 18):
        image = _find_image(source, n)
        if image is None:
            raise FileNotFoundError(f"missing image for index {n} under {source}")
        prompt = _load_prompt(n, source)
        size = _image_size(image)
        w, h = size if size else (None, None)
        items.append(
            {
                "sort_order": n,
                "title": _title_for(n, prompt),
                "prompt": prompt,
                "image_path": image,
                "ext": image.suffix.lstrip(".").lower(),
                "content_type": _content_type(image),
                "aspect_ratio": _aspect_ratio(w, h),
                "width": w,
                "height": h,
            }
        )
    return items


def upload_item(storage: S3Storage, item: dict) -> tuple[str, str]:
    key = storage.build_showcase_key(sort_order=item["sort_order"], ext=item["ext"])
    body = item["image_path"].read_bytes()
    storage.put_public_bytes(
        key=key,
        body=body,
        content_type=item["content_type"],
    )
    url = storage.public_object_url(key)
    return key, url


async def soft_delete_legacy(session: AsyncSession) -> int:
    """Soft-delete old Unsplash / non-S3 showcase rows (no storage_key)."""
    now = utc_now()
    stmt = (
        update(ShowcaseItem)
        .where(
            ShowcaseItem.deleted_at.is_(None),
            ShowcaseItem.storage_key.is_(None),
        )
        .values(deleted_at=now, is_active=False)
    )
    result = await session.execute(stmt)
    return int(result.rowcount or 0)


async def upsert_row(session: AsyncSession, item: dict, storage_key: str, image_url: str) -> str:
    # Prefer matching by storage_key; fall back to first-party sort_order row.
    result = await session.execute(
        select(ShowcaseItem).where(ShowcaseItem.storage_key == storage_key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        result2 = await session.execute(
            select(ShowcaseItem).where(
                ShowcaseItem.sort_order == item["sort_order"],
                ShowcaseItem.storage_key.is_not(None),
            )
        )
        row = result2.scalars().first()
    if row is None:
        result3 = await session.execute(
            select(ShowcaseItem).where(
                ShowcaseItem.sort_order == item["sort_order"],
                ShowcaseItem.deleted_at.is_(None),
            )
        )
        row = result3.scalar_one_or_none()

    if row:
        row.title = item["title"]
        row.prompt = item["prompt"]
        row.image_url = image_url
        row.storage_key = storage_key
        row.aspect_ratio = item["aspect_ratio"]
        row.sort_order = item["sort_order"]
        row.is_active = True
        row.deleted_at = None
        return f"updated #{item['sort_order']} {item['title']}"

    session.add(
        ShowcaseItem(
            id=new_id(),
            title=item["title"],
            prompt=item["prompt"],
            image_url=image_url,
            storage_key=storage_key,
            aspect_ratio=item["aspect_ratio"],
            sort_order=item["sort_order"],
            is_active=True,
        )
    )
    return f"created #{item['sort_order']} {item['title']}"


async def run(source: Path, *, dry_run: bool = False) -> None:
    items = collect_items(source)
    print(f"collected {len(items)} assets from {source}")

    storage = get_s3_storage()
    if not storage.configured:
        raise SystemExit("S3 not configured (AWS_* / S3_* in .env)")

    if dry_run:
        for item in items:
            key = storage.build_showcase_key(sort_order=item["sort_order"], ext=item["ext"])
            print(
                f"[dry-run] #{item['sort_order']} {item['title']} "
                f"{item['image_path'].name} -> {key} "
                f"aspect={item['aspect_ratio']} prompt_chars={len(item['prompt'])}"
            )
        return

    factory = get_session_factory()
    async with factory() as session:
        deleted = await soft_delete_legacy(session)
        print(f"soft-deleted {deleted} legacy showcase row(s)")

        for item in items:
            key, url = upload_item(storage, item)
            msg = await upsert_row(session, item, key, url)
            print(f"{msg}\n  {url}")

        await session.commit()

    await dispose_engine()
    print("showcase seed done")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed homepage showcase from local images")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/Users/zx/Desktop/image"),
        help="Folder with N.jpeg|png + N.txt",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse assets and print plan without S3/DB writes",
    )
    args = parser.parse_args()
    if not args.source.is_dir():
        raise SystemExit(f"source folder not found: {args.source}")
    asyncio.run(run(args.source, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
