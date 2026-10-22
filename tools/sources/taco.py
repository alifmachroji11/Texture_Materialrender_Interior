"""Parser halaman produk TACO HPL (taco.co.id).

Situs TACO memakai Next.js: data produk ada di payload RSC
(self.__next_f.push) sebagai objek {"product": {...}}. Halaman daftar produk
dimuat di sisi klien dari manage.taco.co.id, jadi penemuan produk dilakukan
dengan menelusuri "relatedProducts" dari halaman produk awal.

Catatan data (dicek Oktober 2026):
- "title" = kode produk (mis. "TH 7207 FC"), "sku" = nama motif (mis. "Cream Weave")
- images[].downloadUrl = file asli di manage.taco.co.id
- Gambar adalah shade card, bukan satu lembar penuh 1220 x 2440 mm, sehingga
  luasan fisik yang tergambar tidak diketahui.
"""

import json
import re

BRAND = "TACO"
KATEGORI = "HPL"
BASE = "https://taco.co.id/en/products/laminates"  # situs me-redirect ke jalur kanonis berdasarkan slug
HPL_CATEGORY = "taco-hpl"
DISCLAIMER = ("Menurut TACO: shade card yang ditampilkan bersifat indikatif, bukan representasi "
              "persis warna dan tekstur produk.")

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.S)


def _payload(page_html):
    parts = _PUSH.findall(page_html)
    return "".join(json.loads(f'"{p}"') for p in parts)


def _balanced_object(text, start):
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError("objek JSON tidak tertutup")


def _product_object(page_html):
    data = _payload(page_html)
    i = data.find('{"product":{')
    if i < 0:
        raise ValueError("data produk tidak ditemukan")
    return json.loads(_balanced_object(data, i))["product"]


def _is_hpl(cats):
    return any(c.get("slug") == HPL_CATEGORY for c in cats or [])


def _group(cats):
    """Subkategori motif (Woodgrain, Pattern, Solid, ...)."""
    for c in cats or []:
        if c.get("slug") not in ("laminates", HPL_CATEGORY):
            return c
    return None


def product_url(p):
    g = _group(p.get("categories"))
    return f"{BASE}/{g['slug']}/{HPL_CATEGORY}/{p['slug']}" if g else None


def _sheet_cm(text):
    m = re.search(r"(\d+(?:\.\d+)?)\s*mm\s*x\s*(\d+(?:\.\d+)?)\s*mm", text or "")
    return (float(m.group(1)) / 10, float(m.group(2)) / 10) if m else None


def parse_page(page_html, page_url):
    p = _product_object(page_html)
    if not _is_hpl(p.get("categories")):
        return []
    if not p.get("images"):
        return []
    img = p["images"][0]
    info = {i["info_name"]: i["info_value"] for i in p.get("product_info") or []}
    kode = " ".join(p["title"].split())
    group = _group(p.get("categories"))
    suffix = kode.split()[-1] if len(kode.split()) >= 3 else None
    return [{
        "merek": BRAND,
        "kategori": KATEGORI,
        "seri": group["title"] if group else "HPL",
        "kode": kode,
        "nama": " ".join((p.get("sku") or "").split()) or kode,
        "ukuran_produk": info.get("Dimension"),
        "ukuran_cm": None,
        "ukuran_lembar_cm": _sheet_cm(info.get("Dimension")),
        "finishing": None,
        "warna": None,
        "image_url": img.get("downloadUrl") or img["url"],
        "page_url": page_url,
        "atribut": {
            "kode_akhiran": suffix,
            "tebal": info.get("Thickness"),
            "penggunaan": info.get("Usage"),
            "nama_file_resmi": img.get("name"),
        },
        "catatan": ("Gambar shade card dari situs resmi TACO, resolusi asli. TACO tidak menyebut "
                    "luasan fisik yang tergambar; kalau rasio gambar sama dengan rasio lembar, "
                    "luasan diperkirakan satu lembar penuh, selain itu skala perlu dikira-kira. "
                    + DISCLAIMER),
    }]


def related_urls(page_html):
    data = _payload(page_html)
    out = []
    i = data.find('"relatedProducts":[')
    if i < 0:
        return out
    j = data.index("[", i)
    wrapped = _balanced_object("{\"x\":" + data[j:], 0)  # bungkus array supaya bisa dipotong seimbang
    for r in json.loads(wrapped)["x"]:
        if _is_hpl(r.get("categories")):
            u = product_url(r)
            if u:
                out.append(u)
    return out


def discover(fetch_text, urls, limit=40):
    """Telusuri relatedProducts mulai dari halaman produk awal (BFS)."""
    seen, queue, found = set(), list(urls), []
    while queue and len(found) < limit:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        html = fetch_text(url)
        if parse_page(html, url):
            found.append(url)
        queue.extend(u for u in related_urls(html) if u not in seen)
    return found
