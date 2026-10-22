"""Pustaka sintesis tekstur prosedural bersama (noise periodik, material, peta turunan).

Semua noise dibuat lewat filter FFT sehingga periodik: tekstur otomatis seamless.
"""

import numpy as np

NORMAL_CONVENTION = "OpenGL (Y+)"

# ---------- noise periodik ----------
# Parameter n boleh int (persegi) atau tuple (tinggi, lebar). Frekuensi dinyatakan
# dalam siklus per sisi terpendek, sehingga fitur tetap isotropik di gambar persegi panjang.

def hw(n):
    return (n, n) if np.isscalar(n) else tuple(n)


def periodic_noise(n, rng, cx, cy=None):
    """Noise Gaussian periodik; cx/cy = frekuensi potong (siklus per sisi terpendek)."""
    cy = cx if cy is None else cy
    h, w = hw(n)
    s = min(h, w)
    fy, fx = np.meshgrid(np.fft.fftfreq(h) * s, np.fft.fftfreq(w) * s, indexing="ij")
    filt = np.exp(-((fx / cx) ** 2 + (fy / cy) ** 2))
    spec = np.fft.fft2(rng.standard_normal((h, w))) * filt
    out = np.real(np.fft.ifft2(spec))
    return (out - out.mean()) / (out.std() + 1e-9)


def fractal(n, rng, base, octaves=4, gain=0.5, aniso=1.0):
    total, amp, norm = np.zeros(hw(n)), 1.0, 0.0
    for i in range(octaves):
        c = base * 2 ** i
        total += amp * periodic_noise(n, rng, c, c * aniso)
        norm += amp
        amp *= gain
    return total / norm


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    t = t[..., None]
    return np.asarray(a) * (1 - t) + np.asarray(b) * t


def grid(n):
    h, w = hw(n)
    v, u = np.meshgrid(np.arange(h) / h, np.arange(w) / w, indexing="ij")
    return u, v  # x, y dalam [0, 1)


def short(n):
    return min(hw(n))


# ---------- peta turunan ----------

def normal_from_height(h, strength):
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
    nx, ny, nz = -dx * strength, dy * strength, np.ones_like(h)  # OpenGL: Y ke atas
    length = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    nrm = np.stack([nx, ny, nz], axis=-1) / length[..., None]
    return ((nrm * 0.5 + 0.5) * 255).round().astype(np.uint8)


def to_u8(rgb):
    return (np.clip(rgb, 0, 1) * 255).round().astype(np.uint8)


# ---------- material ----------

def granite_speckle(n, rng, base, chips, mottle=0.06):
    """Granit butiran: warna dasar + beberapa lapis butir (chip) berwarna."""
    rgb = np.ones(hw(n) + (3,)) * np.asarray(base)
    rgb *= 1 + mottle * fractal(n, rng, 6, octaves=3)[..., None]
    height = np.zeros(hw(n))
    for color, density, size in chips:
        f = periodic_noise(n, rng, size)
        thr = np.quantile(f, 1 - density)
        m = smoothstep(thr, thr + 0.35, f)
        rgb = mix(rgb, color, m)
        height += m * 0.3
    rgb *= 1 + 0.03 * periodic_noise(n, rng, short(n) / 4)[..., None]
    return rgb, height


def marble_look(n, rng, base, vein, k=(2, 1), turb=1.6, sharp=10, accent=None):
    """Granit motif marmer (urat). Frekuensi bilangan bulat menjaga seamless."""
    x, y = grid(n)
    t = fractal(n, rng, 1.5, octaves=5, gain=0.45)
    phase = 2 * np.pi * (k[0] * x + k[1] * y) + turb * t
    line = 1 - np.abs(np.sin(phase))
    v1 = line ** sharp + 0.35 * line ** (sharp / 4)  # urat tajam + halo lembut
    t2 = fractal(n, rng, 2, octaves=5, gain=0.5)
    phase2 = 2 * np.pi * (k[1] * x - k[0] * y) + turb * 1.3 * t2
    v2 = (1 - np.abs(np.sin(phase2))) ** (sharp * 2.5)
    cloud = fractal(n, rng, 2, octaves=4)
    rgb = np.ones(hw(n) + (3,)) * np.asarray(base)
    rgb *= 1 + 0.04 * cloud[..., None]
    rgb = mix(rgb, vein, np.clip(v1 * 0.85, 0, 1))
    rgb = mix(rgb, accent if accent is not None else vein, np.clip(v2 * 0.6, 0, 1))
    rgb *= 1 + 0.015 * periodic_noise(n, rng, short(n) / 6)[..., None]
    return rgb, (v1 + v2) * 0.1


def wood(n, rng, light, dark, rings=18, warp=1.3, fiber=0.10):
    """Motif serat kayu HPL; serat memanjang searah sumbu X."""
    x, y = grid(n)
    w = fractal(n, rng, 1.0, octaves=4, aniso=4.0)
    phase = 2 * np.pi * rings * y + warp * w + 0.6 * np.sin(2 * np.pi * x)
    ring = 0.5 + 0.5 * np.sin(phase)
    ring = ring ** 2.2
    fib = periodic_noise(n, rng, 4, 260)
    fib2 = periodic_noise(n, rng, 10, 520)
    tone = np.clip(ring * 0.75 + 0.12 * fib + 0.06 * fib2 + 0.1 * fractal(n, rng, 2), 0, 1)
    rgb = mix(np.ones(hw(n) + (3,)) * np.asarray(light), dark, tone)
    pores = periodic_noise(n, rng, 30, 700)
    pore_m = smoothstep(2.2, 3.0, pores)
    rgb = mix(rgb, np.asarray(dark) * 0.7, pore_m * 0.6)
    rgb *= 1 + fiber * 0.3 * fib[..., None]
    height = -pore_m * 0.8 + fib * 0.05
    return rgb, height


def solid(n, rng, color, grain=0.006):
    rgb = np.ones(hw(n) + (3,)) * np.asarray(color)
    rgb *= 1 + grain * periodic_noise(n, rng, short(n) / 3)[..., None]
    height = periodic_noise(n, rng, short(n) / 5) * 0.05
    return rgb, height


def concrete(n, rng, base):
    rgb = np.ones(hw(n) + (3,)) * np.asarray(base)
    rgb *= 1 + 0.07 * fractal(n, rng, 3, octaves=5)[..., None]
    rgb *= 1 + 0.025 * periodic_noise(n, rng, short(n) / 5)[..., None]
    p = periodic_noise(n, rng, 180)
    pores = smoothstep(2.6, 3.2, p)
    rgb = mix(rgb, np.asarray(base) * 0.55, pores)
    height = -pores + 0.1 * fractal(n, rng, 20, octaves=3)
    return rgb, height


# ---------- warna ----------

def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
