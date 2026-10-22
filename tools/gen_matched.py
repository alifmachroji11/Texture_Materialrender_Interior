"""Generator tekstur GENERIK yang dibuat mirip produk asli (referensi).

Masukan: .inbox/ref/<id>.json + gambar referensi (dibuat oleh fetch_reference.py).
Gambar referensi hanya dianalisis; yang disimpan ke repo adalah tekstur baru hasil
sintesis (lihat matchlib.py), bukan gambar merek.

Model:
- spectral : butiran, semen, solid, kayu serat lurus, tenun (ADSN + histogram Lab)
- veined   : marmer berurat tegas (latar ADSN + urat prosedural yang diukur dari referensi)

Pakai:
  python tools/gen_matched.py            # semua referensi yang belum dibuat
  python tools/gen_matched.py --force    # buat ulang semua
  python tools/gen_matched.py --only roman-gt609754fr
"""

import argparse
import json
import zlib
from datetime import date

import numpy as np
from PIL import Image

import matchlib as ml
from common import ROOT, make_thumb, map_info, product_dir, product_json_path, slug, write_json
from texlib import NORMAL_CONVENTION, fractal, grid, normal_from_height, smoothstep, to_u8

REF_DIR = ROOT / ".inbox" / "ref"

# Marmer dengan urat tajam yang tidak bisa dibentuk oleh model spectral.
# Marmer berawan/berpita (dCaesar, dDurham, Sahara Marble) cukup dengan spectral:
# pita dan awan searahnya sudah ikut terbawa oleh spektrum referensi.
VEINED = {
    "roman-gt809806fr",   # dBasque Nero
    "roman-gt809811fr",   # dBrillante Carrara
}

# Produk warna polos yang fotonya membawa pantulan cahaya: semua variasi skala besar dibuang.
FLAT = {
    "roman-gt602215r",    # Alaska Day
    "roman-gt602216r",    # Alaska Night
}

REF_MARGIN = 0.02  # potong 2% tiap tepi: buang garis bingkai/bayangan tepi pada foto keping

GRANIT_PX_PER_CM = 24
HPL_PATCH_CM = 60
HPL_PX = 2048
TACO_SHEET_CM = (122.0, 244.0)
TACO_ASSUMED_PX_PER_CM = 32.0  # shade card yang luasannya tidak disebut (perkiraan)

# Roughness (0 = cermin, 1 = doff penuh) dan kekuatan normal per finishing. Nilai perkiraan.
FINISH = {
    "Polished Glossy": (0.06, 0.8),
    "Glossy": (0.10, 0.8),
    "Gloss on matt": (0.30, 1.2),
    "Matt": (0.55, 1.5),
    None: (0.45, 1.5),  # HPL TACO: finishing tidak disebut di situs
}


def px8(v):
    return max(8, int(round(v / 8)) * 8)


def plan_geometry(ref, img_w, img_h):
    """Tentukan skala referensi (px/cm) dan ukuran keluaran (px, cm)."""
    if ref["kategori"] == "Granit":
        w_cm, h_cm = ref["ukuran_cm"]["w"], ref["ukuran_cm"]["h"]
        ref_ppc = img_w / w_cm
        out = (px8(h_cm * GRANIT_PX_PER_CM), px8(w_cm * GRANIT_PX_PER_CM))
        cover = {"w": w_cm, "h": h_cm}
        skala_perkiraan = False
    else:
        a, b = TACO_SHEET_CM
        full_sheet = abs(min(img_w, img_h) / max(img_w, img_h) - a / b) < 0.01 * (a / b)
        ref_ppc = min(img_w, img_h) / a if full_sheet else TACO_ASSUMED_PX_PER_CM
        out = (HPL_PX, HPL_PX)
        cover = {"w": HPL_PATCH_CM, "h": HPL_PATCH_CM}
        skala_perkiraan = True
    out_ppc = out[1] / cover["w"]
    return ref_ppc, out, out_ppc, cover, skala_perkiraan


def synth_spectral(lab, shape, scale, rng):
    src = ml.resize_lab(lab, (max(8, round(lab.shape[0] * scale)), max(8, round(lab.shape[1] * scale))))
    out = ml.adsn(src, shape, rng)
    out = ml.add_fine_detail(out, scale, rng, src[..., 0])
    return ml.match_histogram(out, src)


def vein_field(shape, rng, angle, freq, width_px, turb, broken):
    """Medan urat periodik [0,1] dengan lebar urat dalam piksel.

    Garis = titik nol sin(fase), fase linear + turbulensi fraktal. `broken` mengatur
    seberapa banyak ruas urat memudar/putus seperti marmer asli.
    """
    h, w = shape
    s = min(h, w)
    x, y = grid(shape)
    kx = int(round(freq * np.cos(angle) * w / s))
    ky = int(round(freq * np.sin(angle) * h / s))
    if kx == 0 and ky == 0:
        kx = 1
    t = fractal(shape, rng, 1.0, octaves=7, gain=0.5)
    phase = np.pi * (kx * x + ky * y) + turb * t  # satu garis per periode pi
    d = np.abs(np.sin(phase)) / (np.pi * np.hypot(kx / w, ky / h))  # ~jarak ke garis (px)
    core = 1 - smoothstep(0.35 * width_px, width_px, d)
    fade = smoothstep(-0.5, 0.5, fractal(shape, rng, 2.0, octaves=3))
    return np.clip(core * (1 - broken + broken * fade), 0, 1)


def synth_veined(lab, shape, scale, rng, px_per_cm):
    va = ml.vein_analysis(lab)
    base = ml.inpaint_veins(lab, va["mask"])
    out = synth_spectral(base, shape, scale, rng)
    a = va["grad_angle"]  # arah gradien fase = tegak lurus garis urat (sama seperti tensor struktur)
    # (sudut, frekuensi, lebar cm, turbulensi, putus-putus): urat utama, urat sejajar halus, retakan silang
    families = [(a, 2.0, 0.22, 0.35, 0.4),
                (a + np.radians(8), 3.0, 0.12, 0.45, 0.6),
                (a - np.radians(6), 5.0, 0.06, 0.5, 0.7),
                (a - np.radians(40), 4.0, 0.05, 0.6, 0.8)]
    vcol = va["color"]
    for ang, freq, w_cm, turb, broken in families:
        v = vein_field(shape, rng, ang, freq, max(1.2, w_cm * px_per_cm), turb, broken)
        var = fractal(shape, rng, 3, octaves=3)[..., None] * np.array([4.0, 1.0, 1.0])
        out = out * (1 - v[..., None]) + (vcol + var) * v[..., None]
    return out, va


def write_maps(out_dir, rgb, L, finishing):
    rough_base, nstr = FINISH.get(finishing, FINISH[None])
    hp = L - ml.blur(L, 6)
    height = hp / (hp.std() + 1e-6) * 0.15
    rng = np.random.default_rng(7)
    rough = np.clip(rough_base + 0.03 * fractal(L.shape, rng, 8, octaves=3) + 0.02 * height, 0, 1)
    paths = {"albedo": out_dir / "albedo.png", "normal": out_dir / "normal.png",
             "roughness": out_dir / "roughness.png"}
    Image.fromarray(to_u8(rgb), "RGB").save(paths["albedo"], optimize=True)
    Image.fromarray(normal_from_height(height, nstr), "RGB").save(paths["normal"], optimize=True)
    Image.fromarray(to_u8(rough), "L").save(paths["roughness"], optimize=True)
    return paths, rough_base


def build(ref_id, force=False):
    ref = json.loads((REF_DIR / f"{ref_id}.json").read_text(encoding="utf-8"))
    prefix = {"Roman": "RMN", "TACO": "TCO"}[ref["merek"]]
    kode = f"GEN-{prefix}-{ref['kode'].replace(' ', '')}"
    jpath = product_json_path("Generik", kode)
    if jpath.exists() and not force:
        return None

    lab = ml.load_lab(ROOT / ref["gambar"])
    ref_ppc, shape, out_ppc, cover, skala_perkiraan = plan_geometry(ref, lab.shape[1], lab.shape[0])
    # Referensi yang lebih luas dari tekstur (lembar HPL) cukup dipakai bagian tengahnya.
    need_h, need_w = round(cover["h"] * ref_ppc), round(cover["w"] * ref_ppc)
    if lab.shape[0] > need_h or lab.shape[1] > need_w:
        y0, x0 = max(0, (lab.shape[0] - need_h) // 2), max(0, (lab.shape[1] - need_w) // 2)
        lab = lab[y0:y0 + need_h, x0:x0 + need_w]
    m = int(min(lab.shape[:2]) * REF_MARGIN)
    lab = lab[m:lab.shape[0] - m, m:lab.shape[1] - m]
    lab = ml.remove_lighting(lab)
    if ref_id in FLAT:
        r = min(lab.shape[:2]) / 10
        for c in range(3):
            lab[..., c] = lab[..., c] - ml.blur(lab[..., c], r) + lab[..., c].mean()
    scale = out_ppc / ref_ppc
    rng = np.random.default_rng(zlib.crc32(kode.encode()))
    model = "veined" if ref_id in VEINED else "spectral"
    if model == "veined":
        out_lab, _ = synth_veined(lab, shape, scale, rng, out_ppc)
    else:
        out_lab = synth_spectral(lab, shape, scale, rng)
    rgb = ml.lab_to_srgb(out_lab)

    out_dir = product_dir(ref["kategori"], "Generik", ref["seri"], kode)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths, rough_base = write_maps(out_dir, rgb, out_lab[..., 0], ref["finishing"])
    sim = ml.similarity(lab, out_lab, out_ppc, ref_ppc)

    pid = slug(kode)
    catatan = ("Tekstur generik buatan sendiri yang dibuat mirip produk referensi (warna, ukuran butir/serat, "
               "arah motif). Bukan foto dan bukan produk asli; pola tidak identik. Cek sampel fisik sebelum "
               "spesifikasi.")
    if model == "veined":
        catatan += " Urat marmer dibuat prosedural, sehingga bentuk dan letak urat berbeda dari produk asli."
    if ref["kategori"] == "Granit":
        catatan += " Dibuat seamless (tanpa nat); tambahkan nat sendiri di model."
    if skala_perkiraan:
        catatan += " Skala motif diperkirakan dari shade card TACO; cek ulang ukuran serat."
    meta = {
        "id": pid,
        "source_type": "generic",
        "subtipe": "mirip_produk",
        "kategori": ref["kategori"],
        "merek": "Generik",
        "seri": ref["seri"],
        "kode": kode,
        "nama": f"{ref['kategori']} mirip {ref['nama']}",
        "ukuran_produk": None,
        "ukuran_fisik_cm": cover,
        "ukuran_fisik_perkiraan": skala_perkiraan,
        "finishing": ref["finishing"],
        "warna": None,
        "tileable": True,
        "maps": {k: map_info(p) for k, p in paths.items()},
        "normal_convention": NORMAL_CONVENTION,
        "roughness_dasar": rough_base,
        "thumb": make_thumb(paths["albedo"], pid),
        "referensi": {
            "merek": ref["merek"], "seri": ref["seri"], "kode": ref["kode"], "nama": ref["nama"],
            "ukuran_produk": ref["ukuran_produk"], "finishing": ref["finishing"],
            "url": ref["url"], "diakses_tanggal": ref["diakses_tanggal"],
        },
        "metode": model,
        "skor_kemiripan": sim,
        "sumber": {"url": None, "diakses_tanggal": None,
                   "keterangan": f"Sintesis tools/gen_matched.py ({model}) dari analisis referensi"},
        "kode_terverifikasi": False,
        "catatan": catatan,
        "dibuat": date.today().isoformat(),
    }
    write_json(jpath, meta)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="id referensi, mis. roman-gt609754fr")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    ids = sorted(p.stem for p in REF_DIR.glob("*.json"))
    if args.only:
        ids = [i for i in ids if i == args.only]
    if not ids:
        raise SystemExit(f"Tidak ada referensi di {REF_DIR}. Jalankan fetch_reference.py dulu.")
    for ref_id in ids:
        meta = build(ref_id, force=args.force or bool(args.only))
        if meta is None:
            print(f"lewati {ref_id} (sudah ada)")
            continue
        a, s = meta["maps"]["albedo"], meta["skor_kemiripan"]
        print(f"{meta['kode']:<22} {meta['metode']:<8} {a['px_w']}x{a['px_h']}  "
              f"dE={s['delta_e_rata2']} spek={s['selisih_spektrum_log10']} korelasi={s['korelasi_maks']}", flush=True)


if __name__ == "__main__":
    main()
