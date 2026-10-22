"""Analisis gambar referensi dan sintesis tekstur baru yang mirip secara statistik.

Inti metodenya: Asymptotic Discrete Spot Noise (Galerne, Gousseau & Morel, 2011).
Tekstur keluaran dibangun dari noise acak yang dikonvolusi dengan "spot" hasil
komponen periodik gambar referensi, lalu histogram tiap kanal Lab disamakan.
Hasilnya punya spektrum (ukuran butir, arah serat) dan palet warna yang sama,
tetapi susunan pikselnya baru dan acak (bukan salinan) serta otomatis seamless.

Gambar referensi hanya dibaca dari .inbox/ dan tidak pernah disimpan ke repo.
"""

import numpy as np
from PIL import Image, ImageFilter

# ---------- warna: sRGB <-> CIELAB (D65) ----------

_M = np.array([[0.4124564, 0.3575761, 0.1804375],
               [0.2126729, 0.7151522, 0.0721750],
               [0.0193339, 0.1191920, 0.9503041]])
_MI = np.linalg.inv(_M)
_WHITE = np.array([0.95047, 1.0, 1.08883])


def srgb_to_lab(rgb):
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = c @ _M.T / _WHITE
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def lab_to_srgb(lab):
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], -1)
    xyz = np.where(f > 6 / 29, f ** 3, 3 * (6 / 29) ** 2 * (f - 4 / 29)) * _WHITE
    c = np.clip(xyz @ _MI.T, 0, None)
    return np.clip(np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055), 0, 1)


def load_lab(path):
    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.float64) / 255
    return srgb_to_lab(rgb)


def resize_lab(lab, shape):
    """Ubah ukuran per kanal (Lanczos, float)."""
    h, w = shape
    chans = [np.asarray(Image.fromarray(lab[..., c].astype(np.float32), "F").resize((w, h), Image.LANCZOS))
             for c in range(3)]
    return np.stack(chans, -1).astype(np.float64)


# ---------- koreksi pencahayaan foto ----------

def remove_lighting(lab, order=2):
    """Buang gradasi cahaya yang sangat halus (permukaan polinomial orde 2) dari L.

    Gradasi skala seluruh keping hampir selalu efek foto/pantulan, bukan motif.
    """
    h, w = lab.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    x = x / w - 0.5
    y = y / h - 0.5
    terms = [np.ones_like(x)]
    for i in range(1, order + 1):
        for j in range(i + 1):
            terms.append(x ** (i - j) * y ** j)
    A = np.stack([t.ravel() for t in terms], 1)
    L = lab[..., 0]
    step = max(1, (h * w) // 200_000)  # cukup sampel untuk fitting
    coef, *_ = np.linalg.lstsq(A[::step], L.ravel()[::step], rcond=None)
    trend = (A @ coef).reshape(h, w)
    out = lab.copy()
    out[..., 0] = L - trend + L.mean()
    return out


# ---------- sintesis spektral (ADSN) ----------

def periodic_component(u):
    """Dekomposisi periodik + halus (Moisan, 2011) per kanal; buang artefak tepi FFT."""
    h, w = u.shape[:2]
    v = np.zeros_like(u)
    v[0] += u[-1] - u[0]
    v[-1] += u[0] - u[-1]
    v[:, 0] += u[:, -1] - u[:, 0]
    v[:, -1] += u[:, 0] - u[:, -1]
    q = np.arange(h).reshape(-1, 1)
    r = np.arange(w).reshape(1, -1)
    denom = 2 * np.cos(2 * np.pi * q / h) + 2 * np.cos(2 * np.pi * r / w) - 4
    denom[0, 0] = 1
    out = np.empty_like(u)
    for c in range(u.shape[2]):
        S = np.fft.fft2(v[..., c]) / denom
        S[0, 0] = 0
        out[..., c] = u[..., c] - np.real(np.fft.ifft2(S))
    return out


def adsn(src, shape, rng):
    """Tekstur Gaussian seukuran `shape` dengan autokorelasi yang sama seperti `src`.

    Satu noise putih dipakai bersama untuk semua kanal, sehingga korelasi antarwarna terjaga.
    """
    H, W = shape
    p = periodic_component(src)
    h, w = p.shape[:2]
    if h > H or w > W:  # referensi lebih besar: potong bagian tengah
        y0, x0 = max(0, (h - H) // 2), max(0, (w - W) // 2)
        p = p[y0:y0 + min(h, H), x0:x0 + min(w, W)]
        h, w = p.shape[:2]
    mean = p.reshape(-1, 3).mean(0)
    spot = np.zeros((H, W, 3))
    spot[:h, :w] = (p - mean) / np.sqrt(h * w)
    noise = np.fft.fft2(rng.standard_normal((H, W)))
    out = np.empty((H, W, 3))
    for c in range(3):
        out[..., c] = np.real(np.fft.ifft2(np.fft.fft2(spot[..., c]) * noise)) + mean[c]
    return out


def add_fine_detail(lab, upscale, rng, src_L):
    """Tambahkan detail di atas Nyquist referensi (yang hilang karena upscale).

    src_L = kanal L referensi yang sudah di-upscale ke skala keluaran. Amplitudo
    detail mengikuti hukum pangkat yang di-fit dari spektrum radial src_L tepat di
    bawah batas Nyquist referensi (0,5/upscale siklus per piksel keluaran).
    """
    if upscale <= 1.05:
        return lab
    k, amp = radial_spectrum(src_L, bins=128)
    cut = 0.5 / upscale
    sel = (k > 0.3 * cut) & (k < 0.85 * cut) & (amp > 0)
    if sel.sum() < 4:
        return lab
    slope, icpt = np.polyfit(np.log(k[sel]), np.log(amp[sel]), 1)
    H, W = lab.shape[:2]
    fy, fx = np.meshgrid(np.fft.fftfreq(H), np.fft.fftfreq(W), indexing="ij")
    kk = np.maximum(np.hypot(fx, fy), 1e-6)
    band = np.clip((kk - cut) / (0.15 * cut), 0, 1)  # transisi halus di atas batas
    A = np.exp(icpt) * kk ** slope * band
    detail = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((H, W))) * A))
    out = lab.copy()
    out[..., 0] += detail
    return out


def match_histogram(x, ref):
    """Petakan distribusi x ke distribusi ref (per kanal, berbasis kuantil)."""
    out = np.empty_like(x)
    for c in range(x.shape[-1]):
        xs = x[..., c].ravel()
        order = np.argsort(xs)
        q = np.sort(ref[..., c].ravel())
        mapped = np.interp(np.linspace(0, 1, xs.size), np.linspace(0, 1, q.size), q)
        flat = np.empty_like(xs)
        flat[order] = mapped
        out[..., c] = flat.reshape(x.shape[:-1])
    return out


# ---------- analisis ----------

def radial_spectrum(L, bins=64):
    L = L - L.mean()
    F = np.abs(np.fft.fft2(L)) / np.sqrt(L.size)
    h, w = L.shape
    fy, fx = np.meshgrid(np.fft.fftfreq(h), np.fft.fftfreq(w), indexing="ij")
    k = np.hypot(fx, fy).ravel()
    edges = np.linspace(0, 0.5, bins + 1)
    idx = np.digitize(k, edges) - 1
    ok = (idx >= 0) & (idx < bins)
    amp = np.bincount(idx[ok], F.ravel()[ok], bins) / np.maximum(np.bincount(idx[ok], minlength=bins), 1)
    return (edges[:-1] + edges[1:]) / 2, amp


def median_L(L, size):
    im = Image.fromarray(np.clip(L * 2.55, 0, 255).astype(np.uint8), "L")
    return np.asarray(im.filter(ImageFilter.MedianFilter(size)), dtype=np.float64) / 2.55


def blur(a, radius):
    """Gaussian blur via FFT (tepi melingkar; cocok untuk tekstur periodik)."""
    h, w = a.shape
    fy, fx = np.meshgrid(np.fft.fftfreq(h), np.fft.fftfreq(w), indexing="ij")
    g = np.exp(-2 * (np.pi * radius) ** 2 * (fx ** 2 + fy ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def vein_analysis(lab):
    """Deteksi urat marmer: tanda (gelap/terang), cakupan, warna, arah dominan."""
    L = lab[..., 0]
    med = median_L(L, 15)
    r = L - med
    lo, hi = np.quantile(r, [0.003, 0.997])
    dark = -lo > hi
    mad = np.median(np.abs(r - np.median(r))) + 1e-6
    thr = max(4.0, 4 * 1.4826 * mad)
    mask = (r < -thr) if dark else (r > thr)
    coverage = float(mask.mean())
    strong = np.abs(r) * mask
    sel = strong > np.quantile(strong[mask], 0.6) if mask.any() else mask
    if sel.any():
        Lv = np.quantile(L[mask], 0.1 if dark else 0.9)  # warna urat inti, bukan rata-rata tepinya
        color = np.array([Lv, lab[sel][:, 1].mean(), lab[sel][:, 2].mean()])
    else:
        color = lab.reshape(-1, 3).mean(0)
    # arah: tensor struktur dari peta urat yang dihaluskan
    m = blur(mask.astype(np.float64), 3)
    gy, gx = np.gradient(m)
    jxx, jyy, jxy = (gx * gx).mean(), (gy * gy).mean(), (gx * gy).mean()
    grad_angle = 0.5 * np.arctan2(2 * jxy, jxx - jyy)  # arah gradien dominan (tegak lurus urat)
    coherence = np.hypot(jxx - jyy, 2 * jxy) / (jxx + jyy + 1e-12)
    return {"dark": bool(dark), "coverage": coverage, "color": color, "mask": mask,
            "grad_angle": float(grad_angle), "coherence": float(coherence)}


def inpaint_veins(lab, mask, radius=6):
    """Ganti piksel urat dengan rata-rata lokal piksel non-urat (untuk latar)."""
    grown = Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))
    mask = np.asarray(grown) > 0  # lebarkan sedikit supaya halo urat ikut terhapus
    keep = (~mask).astype(np.float64)
    den = blur(keep, radius) + 1e-6
    out = lab.copy()
    for c in range(3):
        fill = blur(lab[..., c] * keep, radius) / den
        out[..., c] = np.where(mask, fill, lab[..., c])
    return out


# ---------- ukuran kemiripan ----------

def similarity(ref_lab, out_lab, out_px_per_cm, ref_px_per_cm):
    """Bandingkan pada skala referensi: warna rata-rata, spektrum, dan bukti bukan salinan."""
    scale = ref_px_per_cm / out_px_per_cm
    H, W = out_lab.shape[:2]
    small = resize_lab(out_lab, (max(8, round(H * scale)), max(8, round(W * scale))))
    d_mean = float(np.linalg.norm(ref_lab.reshape(-1, 3).mean(0) - small.reshape(-1, 3).mean(0)))
    d_std = float(np.abs(ref_lab.reshape(-1, 3).std(0) - small.reshape(-1, 3).std(0)).mean())
    n = min(ref_lab.shape[0], ref_lab.shape[1], small.shape[0], small.shape[1])
    _, a = radial_spectrum(ref_lab[:n, :n, 0])
    _, b = radial_spectrum(small[:n, :n, 0])
    ok = (a > 1e-9) & (b > 1e-9)
    d_spec = float(np.mean(np.abs(np.log10(a[ok]) - np.log10(b[ok])))) if ok.any() else None
    # korelasi silang ternormalisasi maksimum (semua pergeseran): mendekati 1 berarti salinan
    A = ref_lab[:n, :n, 0] - ref_lab[:n, :n, 0].mean()
    B = small[:n, :n, 0] - small[:n, :n, 0].mean()
    xc = np.real(np.fft.ifft2(np.fft.fft2(A) * np.conj(np.fft.fft2(B))))
    ncc = float(xc.max() / (np.sqrt((A * A).sum() * (B * B).sum()) + 1e-12))
    return {"delta_e_rata2": round(d_mean, 2), "selisih_kontras": round(d_std, 2),
            "selisih_spektrum_log10": None if d_spec is None else round(d_spec, 3),
            "korelasi_maks": round(ncc, 3)}
