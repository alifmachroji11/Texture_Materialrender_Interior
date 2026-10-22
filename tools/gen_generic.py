"""Generator tekstur GENERIK (sumber C) secara prosedural.

Semua noise dibuat lewat filter FFT, sehingga hasilnya periodik dan otomatis
seamless (bisa diulang tanpa sambungan). Tekstur ini BUKAN produk merek apa pun.

Pakai: python tools/gen_generic.py [--size 2048]
"""

import argparse
from datetime import date

import numpy as np
from PIL import Image

from common import ROOT, make_thumb, map_info, product_dir, product_json_path, write_json
from texlib import (NORMAL_CONVENTION, concrete, granite_speckle, hexrgb, marble_look,
                    normal_from_height, periodic_noise, solid, to_u8, wood)

CATALOG = [
    dict(kode="GEN-GRN-001", kategori="Granit", seri="Speckle", nama="Granit Speckle Abu Muda",
         finishing="Polished", warna="Abu-abu", cover=60, rough=(0.08, 0.03), nstr=1.5,
         fn=lambda n, r: granite_speckle(n, r, hexrgb("#c9c7c2"), [
             (hexrgb("#6e6c69"), 0.10, 220), (hexrgb("#2f2e2d"), 0.05, 300), (hexrgb("#efedea"), 0.08, 240)])),
    dict(kode="GEN-GRN-002", kategori="Granit", seri="Speckle", nama="Granit Speckle Hitam",
         finishing="Polished", warna="Hitam", cover=60, rough=(0.07, 0.03), nstr=1.5,
         fn=lambda n, r: granite_speckle(n, r, hexrgb("#262626"), [
             (hexrgb("#5a5856"), 0.07, 240), (hexrgb("#9a9894"), 0.025, 320), (hexrgb("#111111"), 0.10, 200)])),
    dict(kode="GEN-GRN-003", kategori="Granit", seri="Marble Look", nama="Granit Motif Marmer Putih Urat Abu",
         finishing="Polished", warna="Putih", cover=60, rough=(0.06, 0.02), nstr=0.6,
         fn=lambda n, r: marble_look(n, r, hexrgb("#ecebe8"), hexrgb("#8d8c8a"), k=(2, 1), accent=hexrgb("#b9b7b3"))),
    dict(kode="GEN-GRN-004", kategori="Granit", seri="Marble Look", nama="Granit Motif Marmer Krem",
         finishing="Matte", warna="Krem", cover=60, rough=(0.45, 0.05), nstr=0.8,
         fn=lambda n, r: marble_look(n, r, hexrgb("#e3d6c0"), hexrgb("#b39a78"), k=(1, 2), turb=2.2, sharp=7)),
    dict(kode="GEN-GRN-005", kategori="Granit", seri="Marble Look", nama="Granit Motif Marmer Hitam Urat Emas",
         finishing="Polished", warna="Hitam", cover=60, rough=(0.06, 0.02), nstr=0.6,
         fn=lambda n, r: marble_look(n, r, hexrgb("#1d1d1f"), hexrgb("#b89a5e"), k=(3, 1), turb=1.8, sharp=14,
                                     accent=hexrgb("#e6e2da"))),
    dict(kode="GEN-HPL-001", kategori="HPL", seri="Kayu", nama="HPL Kayu Oak Natural",
         finishing="Textured", warna="Cokelat muda", cover=60, rough=(0.55, 0.08), nstr=3.0,
         fn=lambda n, r: wood(n, r, hexrgb("#d2ad7c"), hexrgb("#9a6a3b"), rings=16)),
    dict(kode="GEN-HPL-002", kategori="HPL", seri="Kayu", nama="HPL Kayu Walnut Gelap",
         finishing="Textured", warna="Cokelat tua", cover=60, rough=(0.5, 0.08), nstr=3.0,
         fn=lambda n, r: wood(n, r, hexrgb("#7a5235"), hexrgb("#3a2416"), rings=12, warp=1.8)),
    dict(kode="GEN-HPL-003", kategori="HPL", seri="Solid", nama="HPL Solid Putih Doff",
         finishing="Matte", warna="Putih", cover=60, rough=(0.62, 0.02), nstr=0.5,
         fn=lambda n, r: solid(n, r, hexrgb("#f1f0ec"))),
    dict(kode="GEN-HPL-004", kategori="HPL", seri="Solid", nama="HPL Solid Abu Antrasit",
         finishing="Matte", warna="Abu-abu tua", cover=60, rough=(0.6, 0.02), nstr=0.5,
         fn=lambda n, r: solid(n, r, hexrgb("#3c3f42"))),
    dict(kode="GEN-HPL-005", kategori="HPL", seri="Batu & Semen", nama="HPL Motif Semen Ekspos",
         finishing="Textured", warna="Abu-abu", cover=60, rough=(0.75, 0.08), nstr=2.0,
         fn=lambda n, r: concrete(n, r, hexrgb("#9c9a95"))),
]


def build(item, n, seed):
    rng = np.random.default_rng(seed)
    rgb, height = item["fn"](n, rng)
    base_r, var_r = item["rough"]
    rough = np.clip(base_r + var_r * periodic_noise(n, rng, 8) * 0.5 + 0.15 * height * var_r, 0, 1)
    normal = normal_from_height(height, item["nstr"])

    merek = "Generik"
    out = product_dir(item["kategori"], merek, item["seri"], item["kode"])
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "albedo": out / "albedo.png",
        "normal": out / "normal.png",
        "roughness": out / "roughness.png",
    }
    Image.fromarray(to_u8(rgb), "RGB").save(paths["albedo"], optimize=True)
    Image.fromarray(normal, "RGB").save(paths["normal"], optimize=True)
    Image.fromarray(to_u8(rough), "L").save(paths["roughness"], optimize=True)

    pid = item["kode"].lower()
    meta = {
        "id": pid,
        "source_type": "generic",
        "subtipe": "murni",
        "kategori": item["kategori"],
        "merek": merek,
        "seri": item["seri"],
        "kode": item["kode"],
        "nama": item["nama"],
        "ukuran_produk": None,
        "ukuran_fisik_cm": {"w": item["cover"], "h": item["cover"]},
        "finishing": item["finishing"],
        "warna": item["warna"],
        "tileable": True,
        "maps": {k: map_info(p) for k, p in paths.items()},
        "normal_convention": NORMAL_CONVENTION,
        "thumb": make_thumb(paths["albedo"], pid),
        "sumber": {"url": None, "diakses_tanggal": None,
                   "keterangan": f"Prosedural, tools/gen_generic.py, seed {seed}"},
        "kode_terverifikasi": False,
        "catatan": "Tekstur generik buatan prosedural, bukan foto/produk merek apa pun.",
        "dibuat": date.today().isoformat(),
    }
    write_json(product_json_path(merek, item["kode"]), meta)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--only", help="kode tertentu saja, mis. GEN-HPL-001")
    args = ap.parse_args()
    for i, item in enumerate(CATALOG):
        if args.only and item["kode"] != args.only:
            continue
        meta = build(item, args.size, seed=1000 + i)
        print(f"{meta['kode']}: {meta['maps']['albedo']['path']} ({args.size}px)")
    print(f"Selesai. Data di {ROOT / 'data' / 'products' / 'generik'}")


if __name__ == "__main__":
    main()
