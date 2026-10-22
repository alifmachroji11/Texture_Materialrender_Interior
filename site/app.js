(() => {
  "use strict";

  const ITEMS = window.CATALOG || [];
  const ROOT = "../"; // path di catalog relatif ke root repo, situs ada di /site
  const MAP_LABEL = { albedo: "Albedo / Diffuse (warna)", normal: "Normal map", roughness: "Roughness" };
  const FINISH_ID = {
    "Polished Glossy": "Mengilap (polished)", "Polished": "Mengilap (polished)", "Glossy": "Glossy",
    "Matt": "Doff (matte)", "Matte": "Doff (matte)", "Gloss on matt": "Gloss on matt", "Textured": "Bertekstur",
  };

  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const state = { path: [], q: "", source: "", finish: "" };

  const fmtBytes = (b) => (b >= 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.round(b / 1024) + " KB");
  const size = (d) => {
    const u = d.ukuran_fisik_cm;
    return u && u.w && u.h ? `${+u.w} × ${+u.h} cm` : null;
  };
  const fileName = (d, map) => `${d.kode}_${map}.png`.replace(/\s+/g, "-");
  const NO_REF = "Tanpa referensi";
  const refBrand = (d) => (d.referensi && d.referensi.merek) || NO_REF;

  // ---------- filter ----------
  function matches(d, ignorePath) {
    if (state.source && d.subtipe !== state.source) return false;
    if (state.finish && d.finishing !== state.finish) return false;
    if (state.q) {
      const r = d.referensi || {};
      const hay = `${d.kode} ${d.nama} ${d.seri} ${d.kategori} ${d.warna || ""} ${r.merek || ""} ${r.kode || ""} ${(r.kode || "").replace(/\s+/g, "")} ${r.nama || ""}`.toLowerCase();
      if (!state.q.split(/\s+/).every((t) => hay.includes(t))) return false;
    }
    if (!ignorePath) {
      const [k, m, s] = state.path;
      if (k && d.kategori !== k) return false;
      if (m && refBrand(d) !== m) return false;
      if (s && d.seri !== s) return false;
    }
    return true;
  }

  // ---------- pohon kategori > merek referensi > seri ----------
  function renderTree() {
    const visible = ITEMS.filter((d) => matches(d, true));
    const tree = new Map();
    for (const d of visible) {
      if (!tree.has(d.kategori)) tree.set(d.kategori, new Map());
      const brands = tree.get(d.kategori);
      if (!brands.has(refBrand(d))) brands.set(refBrand(d), new Map());
      const series = brands.get(refBrand(d));
      series.set(d.seri, (series.get(d.seri) || 0) + 1);
    }
    const on = (p) => p.length === state.path.length && p.every((v, i) => v === state.path[i]);
    const btn = (lvl, label, n, p) =>
      `<button class="lvl${lvl}${on(p) ? " on" : ""}" data-path='${esc(JSON.stringify(p))}'><span>${esc(label)}</span><span class="n">${n}</span></button>`;
    let html = btn(0, "Semua produk", visible.length, []);
    for (const [k, brands] of [...tree].sort()) {
      const nk = [...brands.values()].reduce((a, s) => a + [...s.values()].reduce((x, y) => x + y, 0), 0);
      html += btn(0, k, nk, [k]);
      const brandList = [...brands].sort((a, b) => (a[0] === NO_REF) - (b[0] === NO_REF) || a[0].localeCompare(b[0]));
      for (const [m, series] of brandList) {
        const nm = [...series.values()].reduce((x, y) => x + y, 0);
        html += btn(1, m, nm, [k, m]);
        if (state.path[0] === k && state.path[1] === m) {
          for (const [s, n] of [...series].sort()) html += btn(2, s, n, [k, m, s]);
        }
      }
    }
    $("#tree").innerHTML = html;
  }

  // ---------- grid ----------
  function badge(d) {
    return d.subtipe === "mirip_produk"
      ? `<span class="badge official">GENERIK · mirip ${esc(d.referensi.merek)}</span>`
      : `<span class="badge generic">GENERIK · tanpa referensi</span>`;
  }

  function renderGrid() {
    const list = ITEMS.filter((d) => matches(d));
    $("#crumb").textContent = state.path.length ? state.path.join(" › ") : "Semua produk";
    $("#count").textContent = `${list.length} produk`;
    $("#empty").hidden = list.length > 0;
    $("#grid").innerHTML = list.map((d) => {
      const a = d.maps.albedo;
      return `<button class="card" data-id="${esc(d.id)}">
        <img src="${esc(ROOT + d.thumb)}" alt="${esc(d.nama)}" loading="lazy">
        <div class="body">
          ${badge(d)}
          <div class="code mono">${esc(d.kode)}</div>
          <div class="name">${esc(d.nama)}</div>
          <div class="meta">${d.referensi ? `Ref. ${esc(d.referensi.kode)} · ` : ""}${esc(d.seri)} · ${a.px_w}×${a.px_h} px</div>
        </div>
      </button>`;
    }).join("");
  }

  function render() { renderTree(); renderGrid(); }

  // ---------- detail ----------
  let current = null;

  function setMode(mode) {
    const stage = $("#stage");
    stage.classList.toggle("tile", mode === "tile");
    document.querySelectorAll(".toggle button").forEach((b) => b.classList.toggle("on", b.dataset.mode === mode));
    $("#tile-note").textContent = mode === "tile"
      ? (current.tileable
        ? "Tekstur seamless: sambungan antarkeping seharusnya tidak terlihat."
        : "Tekstur ini tidak seamless; sambungan mungkin terlihat.")
      : "";
  }

  function row(label, value) {
    return value == null || value === "" ? "" : `<tr><th>${esc(label)}</th><td>${value}</td></tr>`;
  }

  function openDetail(id) {
    const d = ITEMS.find((x) => x.id === id);
    if (!d) return;
    current = d;
    const a = d.maps.albedo;
    const stage = $("#stage");
    stage.style.backgroundImage = `url("${ROOT + a.path}")`;
    stage.style.aspectRatio = `${a.px_w} / ${a.px_h}`;
    setMode("single");

    const ref = d.referensi;
    const sim = d.skor_kemiripan;
    const fisik = size(d);
    const pxPerCm = fisik ? (a.px_w / d.ukuran_fisik_cm.w).toFixed(1) : null;

    const maps = Object.entries(d.maps).map(([name, m]) => `
      <div class="map">
        <div class="row">
          <div><strong>${esc(MAP_LABEL[name] || name)}</strong><br>
            <span class="mono">${m.px_w}×${m.px_h} px · ${fmtBytes(m.bytes)} · PNG</span></div>
          <a class="btn primary" href="${esc(ROOT + m.path)}" download="${esc(fileName(d, name))}">Unduh</a>
        </div>
        <div class="hash mono">SHA-256 ${esc(m.sha256)}</div>
      </div>`).join("");

    const guideSize = fisik
      ? `atur lebar tekstur <strong>${+d.ukuran_fisik_cm.w} cm</strong> dan tinggi <strong>${+d.ukuran_fisik_cm.h} cm</strong>${d.ukuran_fisik_perkiraan ? " (skala perkiraan, cek ukuran serat)" : ""}`
      : "atur ukuran tekstur sesuai skala motif";

    const refBlock = ref ? `
      <h3>Produk referensi (bukan produk ini)</h3>
      <table class="spec">
        ${row("Merek", esc(ref.merek))}
        ${row("Kode produk asli", `<code>${esc(ref.kode)}</code>`)}
        ${row("Nama", esc(ref.nama))}
        ${row("Seri / koleksi", esc(ref.seri))}
        ${row("Ukuran produk", esc(ref.ukuran_produk))}
        ${row("Finishing", esc(FINISH_ID[ref.finishing] || ref.finishing))}
        ${row("Halaman resmi", `<a href="${esc(ref.url)}" target="_blank" rel="noopener">buka</a> · diakses ${esc(ref.diakses_tanggal)}`)}
      </table>` : "";

    const simBlock = sim ? `
      <h3>Skor kemiripan terhadap referensi</h3>
      <table class="spec">
        ${row("Beda warna rata-rata", `ΔE ${sim.delta_e_rata2} <span class="hint">(&lt; 1 praktis tidak terlihat)</span>`)}
        ${row("Beda kontras", `${sim.selisih_kontras} <span class="hint">(ΔL/a/b, makin kecil makin sama)</span>`)}
        ${row("Beda spektrum motif", `${sim.selisih_spektrum_log10} <span class="hint">(log10; &lt; 0,15 ukuran butir/serat sangat mirip)</span>`)}
        ${row("Korelasi pola maks.", `${sim.korelasi_maks} <span class="hint">(1 = salinan; rendah = pola baru)</span>`)}
        ${row("Metode", d.metode === "veined" ? "latar spektral + urat prosedural" : "sintesis spektral (ADSN)")}
      </table>` : "";

    $("#info").innerHTML = `
      ${badge(d)} <span class="badge warn">bukan produk asli</span>
      <h2>${esc(d.nama)}</h2>
      <div class="codeline"><code>${esc(d.kode)}</code><button class="btn" id="copy">Salin kode</button></div>
      <table class="spec">
        ${row("Kategori", esc(d.kategori))}
        ${row("Seri", esc(d.seri))}
        ${row("Luasan tekstur", fisik ? `${fisik} (${pxPerCm} px/cm)${d.ukuran_fisik_perkiraan ? " · <em>skala perkiraan</em>" : ""}` : "tidak diketahui")}
        ${row("Finishing", esc(FINISH_ID[d.finishing] || d.finishing))}
        ${row("Roughness dasar", d.roughness_dasar != null ? `${d.roughness_dasar} (perkiraan dari finishing)` : null)}
        ${row("Warna", esc(d.warna))}
        ${row("Seamless", d.tileable ? "Ya" : "Tidak")}
      </table>
      ${refBlock}
      ${simBlock}
      <h3>Unduh (resolusi asli)</h3>
      <div class="maps">${maps}</div>
      ${d.catatan ? `<h3>Catatan</h3><div class="note">${esc(d.catatan)}</div>` : ""}
      <h3>Pemakaian</h3>
      <ul class="guide">
        <li><strong>SketchUp:</strong> Materials › Create Material › pilih albedo.png, lalu ${guideSize}. Supaya resolusi tidak diturunkan, centang <em>Use maximum texture size</em> di Preferences › Graphics/OpenGL.</li>
        <li><strong>D5 Render:</strong> pakai material dari SketchUp lewat LiveSync, atau ganti peta di panel material (Base Color${d.maps.normal ? ", Normal, Roughness" : ""}).${d.maps.normal ? ` Normal map berkonvensi ${esc(d.normal_convention || "OpenGL (Y+)")}; kalau relief terlihat terbalik, balik kanal hijau (Y).` : ""}</li>
      </ul>`;

    $("#copy").onclick = async (e) => {
      try { await navigator.clipboard.writeText(d.kode); e.target.textContent = "Tersalin ✓"; }
      catch { e.target.textContent = d.kode; }
    };
    $("#detail").showModal();
  }

  // ---------- init ----------
  const finishes = [...new Set(ITEMS.map((d) => d.finishing).filter(Boolean))].sort();
  $("#f-finish").insertAdjacentHTML("beforeend", finishes.map((f) => `<option value="${esc(f)}">${esc(FINISH_ID[f] || f)}</option>`).join(""));

  $("#tree").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-path]");
    if (!b) return;
    state.path = JSON.parse(b.dataset.path);
    render();
  });
  $("#grid").addEventListener("click", (e) => {
    const c = e.target.closest(".card");
    if (c) openDetail(c.dataset.id);
  });
  $("#q").addEventListener("input", (e) => { state.q = e.target.value.trim().toLowerCase(); render(); });
  $("#f-source").addEventListener("change", (e) => { state.source = e.target.value; render(); });
  $("#f-finish").addEventListener("change", (e) => { state.finish = e.target.value; render(); });
  document.querySelectorAll(".toggle button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
  $("#close").addEventListener("click", () => $("#detail").close());
  $("#detail").addEventListener("click", (e) => { if (e.target.id === "detail") $("#detail").close(); });

  if (!ITEMS.length) $("#empty").textContent = "catalog.js kosong. Jalankan: python tools/build_catalog.py";
  render();
})();
