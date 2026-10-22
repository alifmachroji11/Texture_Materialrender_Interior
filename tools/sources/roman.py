"""Parser halaman koleksi RomanGranit (roman.co.id).

Struktur yang dipakai (dicek Oktober 2026):
- spesifikasi koleksi: <div class="collection-specs-overview"> berisi 4 <li>:
  nama koleksi, lini (mood), ukuran, finishing
- tiap produk: <img src=".../Kepingan_...-768x768.jpg"> lalu
  <ul class="product-data-header"> (kode, nama, ukuran) dan
  <ul class="product-data-body"> (pasangan spesifikasi)
Gambar asli = URL thumbnail tanpa akhiran "-WxH".
"""

import html
import re

BRAND = "Roman"
KATEGORI = "Granit"

_SPEC = re.compile(r'<div class="collection-specs-overview.*?<ul class="row">(.*?)</ul>', re.S)
_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.S)
_DESC = re.compile(r"<!-- Icons & Description -->.*?<p>(.*?)</p>", re.S)
_PRODUCT = re.compile(
    r'<img src="(https://roman\.co\.id/wp-content/uploads/[^"]+)">\s*</a>.*?'
    r'<ul class="product-data-header">(.*?)</ul>\s*(?:</div>\s*)?'
    r'<ul class="product-data-body">(.*?)</ul>',
    re.S,
)
_KV = re.compile(r"<div>(.*?)</div>\s*<div>(.*?)</div>", re.S)
_SIZE_SUFFIX = re.compile(r"-\d+x\d+(\.\w+)$")
_COLLECTION_LINK = re.compile(r'https://roman\.co\.id/id/collection/romangranit/[^"/]+/')


def _clean(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def discover(fetch_text, urls, limit=None):
    """Tautan halaman koleksi dari halaman daftar produk."""
    links = set()
    for url in urls:
        links.update(_COLLECTION_LINK.findall(fetch_text(url)))
    return sorted(links)[:limit]


def parse_size(text):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*x\s*(\d+(?:[.,]\d+)?)", text)
    if not m:
        return None
    return float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))


def parse_page(page_html, page_url):
    """Kembalikan daftar dict produk dari satu halaman koleksi."""
    spec = _SPEC.search(page_html)
    if not spec:
        raise ValueError(f"Spesifikasi koleksi tidak ditemukan: {page_url}")
    fields = [_clean(x) for x in _LI.findall(spec.group(1))]
    seri, lini, ukuran, finishing = (fields + [None] * 4)[:4]
    desc = _DESC.search(page_html)
    deskripsi = _clean(desc.group(1)) if desc else None

    products = []
    for img, header, body in _PRODUCT.findall(page_html):
        head = [_clean(x) for x in _LI.findall(header)]
        if len(head) < 3:
            continue
        kode, nama, ukuran_p = head[:3]
        specs = {_clean(k): _clean(v) for k, v in _KV.findall(body)}
        products.append({
            "merek": BRAND,
            "kategori": KATEGORI,
            "seri": seri,
            "kode": kode,
            "nama": nama,
            "ukuran_produk": f"{ukuran_p} cm",
            "ukuran_cm": parse_size(ukuran_p),
            "finishing": finishing,
            "warna": None,
            "image_url": _SIZE_SUFFIX.sub(r"\1", img),
            "image_url_fallback": img,
            "page_url": page_url,
            "atribut": {"lini": lini, "deskripsi_koleksi": deskripsi, **specs},
        })
    return products
