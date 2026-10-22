"""Unduh gambar + data produk resmi sebagai REFERENSI lokal untuk gen_matched.py.

Semua hasil masuk ke .inbox/ref/ (diabaikan git). Gambar merek tidak pernah
disalin ke textures/ dan sebaiknya dihapus setelah tekstur dibuat:
    rm -rf .inbox

Pakai:
  python tools/fetch_reference.py roman --list <url-halaman-daftar>
  python tools/fetch_reference.py roman <url-koleksi> [<url-koleksi> ...]
  python tools/fetch_reference.py taco --list <url-produk-awal> --limit 30
  python tools/fetch_reference.py taco <url-produk> [<url-produk> ...]
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from PIL import Image

from common import ROOT, slug
from sources import roman, taco

SOURCES = {"roman": roman, "taco": taco}
REF_DIR = ROOT / ".inbox" / "ref"
UA = "Mozilla/5.0 (texture-catalog; personal use)"


def fetch(url, final_url=False):
    """Unduh URL. final_url=True juga mengembalikan URL akhir setelah redirect."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        return (body, r.geturl()) if final_url else body


def save_reference(p, today):
    REF_DIR.mkdir(parents=True, exist_ok=True)
    try:
        raw = fetch(p["image_url"])
    except urllib.error.HTTPError:
        if not p.get("image_url_fallback"):
            raise
        p["image_url"] = p["image_url_fallback"]  # file asli tidak ada, pakai yang tersedia
        raw = fetch(p["image_url"])
    rid = f"{slug(p['merek'])}-{slug(p['kode'])}"
    img = REF_DIR / f"{rid}{Path(p['image_url']).suffix.lower() or '.img'}"
    img.write_bytes(raw)
    with Image.open(img) as im:
        im.verify()
    with Image.open(img) as im:
        px_w, px_h = im.size

    # Ukuran keping (cm), orientasinya disamakan dengan gambar.
    size = None
    if p.get("ukuran_cm"):
        w, h = p["ukuran_cm"]
        if (px_w > px_h) != (w > h) and w != h:
            w, h = h, w
        size = {"w": w, "h": h}

    ref = {
        "kategori": p["kategori"], "merek": p["merek"], "seri": p["seri"], "kode": p["kode"],
        "nama": p["nama"], "ukuran_produk": p["ukuran_produk"], "finishing": p["finishing"],
        "atribut": p.get("atribut", {}), "catatan": p.get("catatan"),
        "ukuran_cm": size, "url": p["page_url"], "diakses_tanggal": today,
        "gambar": img.relative_to(ROOT).as_posix(),
    }
    (REF_DIR / f"{rid}.json").write_text(json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")
    return rid, px_w, px_h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("merek", choices=sorted(SOURCES))
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--list", action="store_true", help="hanya tampilkan tautan halaman produk/koleksi yang ditemukan")
    ap.add_argument("--limit", type=int, default=40, help="batas jumlah tautan untuk --list")
    ap.add_argument("--dry-run", action="store_true", help="parse saja, tanpa mengunduh gambar")
    args = ap.parse_args()
    src = SOURCES[args.merek]
    today = date.today().isoformat()

    if args.list:
        def fetch_text(u):
            return fetch(u).decode("utf-8", "replace")
        print("\n".join(src.discover(fetch_text, args.urls, args.limit)))
        return

    total = 0
    for url in args.urls:
        body, url = fetch(url, final_url=True)
        products = src.parse_page(body.decode("utf-8", "replace"), url)
        if not products:
            print(f"PERINGATAN: tidak ada produk terbaca di {url}", file=sys.stderr)
        for p in products:
            if args.dry_run:
                print(f"{p['kode']:<16} {p['nama']:<28} {p['ukuran_produk'] or '-':<18} {p['finishing']}")
                continue
            rid, w, h = save_reference(p, today)
            print(f"{rid}: {w}x{h} px")
            total += 1
    if not args.dry_run:
        print(f"{total} referensi disimpan di {REF_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
