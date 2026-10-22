"""Gabungkan semua metadata produk menjadi site/catalog.js.

Ditulis sebagai JS (window.CATALOG = ...) supaya site/index.html bisa dibuka
langsung lewat file:// tanpa server.

Pakai: python tools/build_catalog.py
"""

import json

from common import PRODUCTS, SITE


def main():
    items = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(PRODUCTS.rglob("*.json"))]
    items.sort(key=lambda d: (d["kategori"], d["source_type"] != "official", d["merek"], d["seri"], d["kode"]))
    SITE.mkdir(parents=True, exist_ok=True)
    body = json.dumps(items, ensure_ascii=False, indent=1)
    (SITE / "catalog.js").write_text(
        "// File hasil generate: python tools/build_catalog.py. Jangan diedit manual.\n"
        f"window.CATALOG = {body};\n",
        encoding="utf-8",
    )
    print(f"site/catalog.js: {len(items)} produk")


if __name__ == "__main__":
    main()
