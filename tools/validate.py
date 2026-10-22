"""Validasi semua metadata produk: skema, file ada, dan px/bytes/sha256 cocok.

Katalog hanya berisi tekstur GENERIK buatan sendiri:
- subtipe "murni"        : tanpa referensi produk
- subtipe "mirip_produk" : dibuat mirip produk asli, wajib mencantumkan referensi

Pakai: python tools/validate.py   (exit code 1 jika ada kesalahan)
"""

import json
import sys

from PIL import Image

from common import MAP_NAMES, PRODUCTS, ROOT, TEXTURES, sha256_file

REQUIRED = ["id", "source_type", "subtipe", "kategori", "merek", "seri", "kode", "nama",
            "ukuran_fisik_cm", "finishing", "warna", "tileable", "maps", "thumb",
            "sumber", "kode_terverifikasi"]
REF_REQUIRED = ["merek", "kode", "nama", "url", "diakses_tanggal"]


def check(d):
    errs = [f"field '{k}' tidak ada" for k in REQUIRED if k not in d]
    if errs:
        return errs
    if d["source_type"] != "generic":
        errs.append(f"source_type harus 'generic', bukan {d['source_type']!r}")
    if d["merek"] != "Generik" or not d["kode"].startswith("GEN-"):
        errs.append("merek wajib 'Generik' dan kode berawalan 'GEN-'")
    if d["subtipe"] == "mirip_produk":
        ref = d.get("referensi") or {}
        errs += [f"referensi.{k} kosong" for k in REF_REQUIRED if not ref.get(k)]
        if ref.get("kode") and d["kode"] == ref["kode"]:
            errs.append("kode tekstur tidak boleh sama dengan kode produk asli")
    elif d["subtipe"] != "murni":
        errs.append(f"subtipe tidak dikenal: {d['subtipe']}")
    if "albedo" not in d["maps"]:
        errs.append("peta albedo wajib ada")
    for name, m in d["maps"].items():
        if name not in MAP_NAMES:
            errs.append(f"nama peta tidak dikenal: {name}")
        f = ROOT / m["path"]
        if not f.exists():
            errs.append(f"file tidak ada: {m['path']}")
            continue
        if f.suffix.lower() != ".png":
            errs.append(f"bukan PNG: {m['path']}")
        with Image.open(f) as im:
            if im.size != (m["px_w"], m["px_h"]):
                errs.append(f"{name}: ukuran px {im.size} != metadata {(m['px_w'], m['px_h'])}")
        if f.stat().st_size != m["bytes"]:
            errs.append(f"{name}: ukuran file berbeda dari metadata")
        if sha256_file(f) != m["sha256"]:
            errs.append(f"{name}: sha256 tidak cocok")
    if not (ROOT / d["thumb"]).exists():
        errs.append(f"thumbnail tidak ada: {d['thumb']}")
    return errs


def stray_files(known):
    """File di textures/ yang tidak dirujuk metadata (mis. gambar merek tertinggal)."""
    return sorted(p.relative_to(ROOT).as_posix() for p in TEXTURES.rglob("*")
                  if p.is_file() and p.relative_to(ROOT).as_posix() not in known)


def main():
    files = sorted(PRODUCTS.rglob("*.json"))
    bad, ids, known = 0, set(), set()
    for p in files:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            errs = check(d)
            if d.get("id") in ids:
                errs.append(f"id ganda: {d['id']}")
            ids.add(d.get("id"))
            known.update(m["path"] for m in d.get("maps", {}).values())
        except json.JSONDecodeError as e:
            errs = [f"JSON rusak: {e}"]
        if errs:
            bad += 1
            print(f"GAGAL {p.relative_to(ROOT)}")
            for e in errs:
                print(f"  - {e}")
    stray = stray_files(known)
    for s in stray:
        print(f"FILE TAK DIKENAL {s}")
    print(f"{len(files)} produk dicek, {bad} bermasalah, {len(stray)} file tak dikenal.")
    sys.exit(1 if bad or stray else 0)


if __name__ == "__main__":
    main()
