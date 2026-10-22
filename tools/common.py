"""Utilitas bersama: path, hash, metadata peta tekstur, thumbnail, JSON."""

import hashlib
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TEXTURES = ROOT / "textures"
THUMBS = ROOT / "thumbs"
PRODUCTS = ROOT / "data" / "products"
SITE = ROOT / "site"

THUMB_PX = 512
SOURCE_TYPES = ("official", "generic")
MAP_NAMES = ("albedo", "normal", "roughness")


def slug(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def product_dir(kategori, merek, seri, kode):
    return TEXTURES / slug(kategori) / slug(merek) / slug(seri) / slug(kode)


def map_info(path, format_asli="PNG"):
    """Metadata satu file peta: dibaca dari file yang sudah tertulis di disk."""
    path = Path(path)
    with Image.open(path) as im:
        w, h = im.size
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "px_w": w,
        "px_h": h,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "format_asli": format_asli,
    }


def make_thumb(src, product_id):
    """Thumbnail WebP untuk pratinjau saja; file asli tidak disentuh."""
    THUMBS.mkdir(parents=True, exist_ok=True)
    out = THUMBS / f"{product_id}.webp"
    with Image.open(src) as im:
        im = im.convert("RGB")
        im.thumbnail((THUMB_PX, THUMB_PX), Image.LANCZOS)
        im.save(out, "WEBP", quality=85)
    return out.relative_to(ROOT).as_posix()


def product_json_path(merek, kode):
    return PRODUCTS / slug(merek) / f"{slug(kode)}.json"


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
