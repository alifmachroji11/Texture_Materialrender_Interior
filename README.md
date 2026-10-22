# Katalog Tekstur Interior

Pustaka tekstur PNG untuk SketchUp dan D5 Render, dengan situs katalog yang berjalan lokal di laptop.
Isinya dikelompokkan per **kategori → merek referensi → seri**, dan setiap tekstur bisa diunduh
dalam resolusi aslinya (albedo, normal, roughness).

> **Penting:** semua tekstur di sini adalah **tekstur generik buatan sendiri**. Sebagian dibuat
> *mirip* produk asli (Roman, TACO) supaya bisa dipakai sebagai pengganti saat render, tetapi
> **bukan foto dan bukan produk asli**. Nama merek dan kode produk asli hanya dicantumkan sebagai
> referensi. Selalu cek sampel fisik di toko sebelum menulis spesifikasi.

## Isi batch 1

| Jenis | Jumlah | Keterangan |
|---|---|---|
| Granit mirip RomanGranit | 25 | ukuran keping asli (60×60 sampai 120×60 cm), 24 px/cm, seamless |
| HPL mirip TACO HPL | 13 | patch seamless 60×60 cm, 2048 px |
| Generik tanpa referensi | 10 | granit dan HPL prosedural, 2048 px |

Setiap tekstur punya `albedo.png`, `normal.png` (OpenGL, Y+), dan `roughness.png`.

## Membuka katalog

```bash
git clone <url-repo>
cd Texture_Materialrender_Interior
git lfs install
git lfs pull          # file PNG disimpan lewat Git LFS
```

Lalu klik dua kali `site/index.html`. Situsnya tidak perlu server. Kalau browser menolak tombol
unduh dari `file://`, jalankan server lokal:

```bash
python -m http.server 8000
# buka http://localhost:8000/site/
```

## Memakai tekstur

**SketchUp**
1. Window › Materials › Create Material, lalu pilih `albedo.png`.
2. Isi lebar/tinggi tekstur sesuai **Luasan tekstur** di halaman detail (misalnya 60 × 60 cm).
3. Preferences › Graphics (OpenGL): centang *Use maximum texture size*. Tanpa ini SketchUp
   menurunkan resolusi tekstur.
4. Tekstur granit dibuat seamless tanpa nat, jadi nat ditambahkan sendiri di model.

**D5 Render**
- Material dari SketchUp ikut terbawa lewat LiveSync. Untuk hasil lebih realistis, isi juga
  Normal dan Roughness di panel material.
- Normal map memakai konvensi OpenGL (Y+). Kalau relief terlihat terbalik, balik kanal hijau.
- Nilai roughness diperkirakan dari finishing (polished ≈ 0,06; matt ≈ 0,55; HPL ≈ 0,45).

## Cara tekstur "mirip produk" dibuat

1. `tools/fetch_reference.py` mengunduh gambar dan data produk resmi (kode, nama, ukuran,
   finishing) ke `.inbox/ref/`. Folder ini **tidak ikut di-commit**.
2. `tools/gen_matched.py` menganalisis gambar referensi lalu membuat tekstur **baru**:
   - **spectral** (butiran, semen, kayu, tenun, marmer berawan): sintesis *Asymptotic Discrete
     Spot Noise* (Galerne dkk., 2011). Spektrum referensi (ukuran butir, arah serat) dan histogram
     warna Lab dipertahankan, tetapi susunan pikselnya acak dan baru. Gradasi cahaya foto dibuang
     dulu.
   - **veined** (dBasque Nero, dBrillante Carrara): latar dibuat secara spektral, lalu urat
     ditambahkan secara prosedural. Warna, arah, dan ketebalan urat diukur dari referensi.
3. Skor kemiripan dihitung otomatis dan ditampilkan di halaman detail:
   - beda warna rata-rata (ΔE);
   - beda spektrum motif;
   - korelasi pola maksimum, yang memastikan hasilnya bukan salinan (1 = salinan).
4. Setelah selesai, hapus referensi: `rm -rf .inbox`.

**Batasan**
- Pola urat marmer dan figur kayu tidak sama persis dengan produk asli; yang dicocokkan adalah
  karakternya.
- Skala motif HPL TACO diperkirakan dari shade card, karena TACO tidak menyebut luasan gambarnya.
- Detail yang lebih halus dari resolusi gambar referensi diekstrapolasi.

## Menambah produk

```bash
pip install -r requirements.txt

# 1. ambil referensi (contoh: satu koleksi Roman)
python tools/fetch_reference.py roman https://roman.co.id/id/collection/romangranit/aberdeen/
# atau cari halaman produk TACO lewat produk terkait
python tools/fetch_reference.py taco --list https://taco.co.id/en/products/laminates/pattern/taco-hpl/th-7207-fc

# 2. buat tekstur, 3. cek, 4. perbarui katalog
python tools/gen_matched.py
python tools/validate.py
python tools/build_catalog.py

# 5. hapus gambar referensi
rm -rf .inbox
```

Kalau koleksinya marmer berurat tajam, tambahkan id referensinya ke `VEINED` di
`tools/gen_matched.py`. Tekstur generik tanpa referensi dibuat dengan `tools/gen_generic.py`.

## Struktur

```
site/                 situs katalog (HTML/CSS/JS statis); catalog.js dibuat otomatis
data/products/        satu JSON metadata per tekstur
textures/<kategori>/generik/<seri>/<kode>/   albedo.png, normal.png, roughness.png (Git LFS)
thumbs/               pratinjau WebP (hanya untuk tampilan)
tools/                generator, parser referensi, validator
```
