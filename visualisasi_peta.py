"""
Visualisasi Peta Interaktif – Simulasi Kebijakan Jawa Timur
============================================================
Script ini membaca:
  1. File GeoJSON kabupaten/kota Jawa Timur
  2. File CSV hasil simulasi kebijakan (policy_simulation_output.csv)

Kemudian menghasilkan SATU file HTML berisi banyak peta choropleth
interaktif dengan navigasi tab, menggunakan folium + geopandas.
"""

from pathlib import Path
import json
import html as html_lib

import numpy as np
import geopandas as gpd
import pandas as pd
import folium
import branca.colormap as cm


# ─── Konfigurasi ────────────────────────────────────────────────────
ROOT = Path(".").resolve()
GEOJSON_PATH = ROOT / "Kabupaten-Kota (Provinsi Jawa Timur).geojson"
CSV_PATH = ROOT / "policy_simulation_output.csv"
OUTPUT_PATH = ROOT / "index.html"
MAPS_DIR = ROOT / "maps"

# Indikator peta tunggal (Baseline saja – skala bebas)
SINGLE_INDICATORS = [
    ("poor_rate_baseline", "Kemiskinan (Baseline)",
     "Tingkat Kemiskinan – Baseline (per 1.000 penduduk)", "YlOrRd", ".1f"),
    ("IPM_baseline", "IPM (Baseline)",
     "IPM – Baseline", "YlGn", ".2f"),
    ("TPT_baseline", "TPT (Baseline)",
     "TPT – Baseline (%)", "PuBu", ".2f"),
]

# Perbandingan absolut S1 vs S2 vs S3 – shared scale per indikator
ABSOLUTE_TRIPLE = [
    # (col_s1, col_s2, col_s3, tab_label, title_s1, title_s2, title_s3, cmap, fmt)
    ("poor_rate_s1", "poor_rate_s2", "poor_rate_s3",
     "Kemiskinan (S1/S2/S3)",
     "S1: Kemiskinan", "S2: Kemiskinan", "S3: Kemiskinan",
     "YlOrRd", ".1f"),
    ("IPM_s1", "IPM_s2", "IPM_s3",
     "IPM (S1/S2/S3)",
     "S1: IPM", "S2: IPM", "S3: IPM",
     "YlGn", ".2f"),
    ("TPT_s1", "TPT_s2", "TPT_s3",
     "TPT (S1/S2/S3)",
     "S1: TPT", "S2: TPT", "S3: TPT",
     "PuBu", ".2f"),
]

# Perbandingan delta S1 vs S2 vs S3 – shared scale per indikator
DELTA_TRIPLE = [
    # (col_s1, col_s2, col_s3, tab_label, title_s1, title_s2, title_s3, cmap, fmt)
    ("delta_poor_rate_s1", "delta_poor_rate_s2", "delta_poor_rate_s3",
     "Δ Kemiskinan (S1/S2/S3)",
     "S1: Δ Kemiskinan", "S2: Δ Kemiskinan", "S3: Δ Kemiskinan",
     "RdYlGn_r", ".4f"),
    ("delta_IPM_s1", "delta_IPM_s2", "delta_IPM_s3",
     "Δ IPM (S1/S2/S3)",
     "S1: Δ IPM", "S2: Δ IPM", "S3: Δ IPM",
     "RdYlGn", ".4f"),
    ("delta_TPT_s1", "delta_TPT_s2", "delta_TPT_s3",
     "Δ TPT (S1/S2/S3)",
     "S1: Δ TPT", "S2: Δ TPT", "S3: Δ TPT",
     "RdYlGn_r", ".4f"),
]


# ─── Fungsi bantu: harmonisasi nama ─────────────────────────────────
def _build_geojson_name(properties: dict) -> str:
    """Bangun nama kabkota dari properti GeoJSON agar cocok dengan CSV."""
    name = properties.get("NAME_2", "").strip()
    tipe = properties.get("TYPE_2", "").strip()

    if name.startswith("Kota "):
        return name
    if tipe.lower() == "kota":
        return f"Kota {name}"
    return f"Kabupaten {name}"


def harmonize_geojson(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Tambah kolom `nama_kabkota` hasil harmonisasi ke GeoDataFrame."""
    names = []
    for _, row in gdf.iterrows():
        props = {
            "NAME_2": row.get("NAME_2", ""),
            "TYPE_2": row.get("TYPE_2", ""),
        }
        names.append(_build_geojson_name(props))
    gdf = gdf.copy()
    gdf["nama_kabkota"] = names
    return gdf


# ─── Warna dari matplotlib ──────────────────────────────────────────
def _sample_colors(cmap_name: str, n: int):
    """Ambil *n* warna HEX dari matplotlib colormap."""
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors

    cmap = plt.get_cmap(cmap_name)
    return [mcolors.to_hex(cmap(i / (n - 1))) for i in range(n)]


# ─── Pembuat satu peta folium ────────────────────────────────────────
def make_choropleth(
    gdf: gpd.GeoDataFrame,
    column: str,
    title: str,
    cmap_name: str = "YlOrRd",
    fmt: str = ".2f",
    vmin_override: float = None,
    vmax_override: float = None,
) -> folium.Map:
    """Buat satu peta folium choropleth interaktif."""

    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=8,
        tiles="cartodbpositron",
    )

    vmin = vmin_override if vmin_override is not None else float(gdf[column].min())
    vmax = vmax_override if vmax_override is not None else float(gdf[column].max())

    colormap = cm.LinearColormap(
        colors=_sample_colors(cmap_name, 8),
        vmin=vmin,
        vmax=vmax,
        caption=title,
    )
    colormap.add_to(m)

    def style_fn(feature):
        val = feature["properties"].get(column, None)
        if val is None:
            fill_color = "#cccccc"
        else:
            fill_color = colormap(val)
        return {
            "fillColor": fill_color,
            "color": "#333333",
            "weight": 1,
            "fillOpacity": 0.75,
        }

    def highlight_fn(feature):
        return {
            "weight": 3,
            "color": "#000000",
            "fillOpacity": 0.9,
        }

    tooltip = folium.GeoJsonTooltip(
        fields=["nama_kabkota", column],
        aliases=["Wilayah", title],
        localize=True,
        sticky=True,
        style="background-color: white; font-size: 12px; padding: 6px;",
    )

    geojson_data = json.loads(gdf.to_json())
    folium.GeoJson(
        geojson_data,
        style_function=style_fn,
        highlight_function=highlight_fn,
        tooltip=tooltip,
        name=title,
    ).add_to(m)

    return m


# ─── Pembungkus HTML dengan tab ──────────────────────────────────────
def build_combined_html(tabs_data: list) -> str:
    """
    Buat satu halaman HTML dengan tab navigasi.

    tabs_data: list of dicts with keys:
      - label: tab button label
      - type: "single" | "triple"
      - src: (for single) path relatif ke file HTML peta
      - src_1, src_2, src_3, title_1, title_2, title_3: (for triple)
    """

    tab_buttons = []
    tab_contents = []

    for i, tab in enumerate(tabs_data):
        active = "active" if i == 0 else ""
        display = "block" if i == 0 else "none"
        tab_id = f"tab_{i}"

        tab_buttons.append(
            f'<button class="tab-btn {active}" '
            f'onclick="switchTab({i})" id="btn_{i}">'
            f'{html_lib.escape(tab["label"])}</button>'
        )

        if tab["type"] == "single":
            tab_contents.append(
                f'<div class="tab-content" id="{tab_id}" '
                f'style="display:{display};">'
                f'<iframe src="{tab["src"]}" '
                f'style="width:100%;height:100%;border:none;" loading="lazy"></iframe>'
                f'</div>'
            )
        elif tab["type"] == "triple":
            t1 = html_lib.escape(tab["title_1"])
            t2 = html_lib.escape(tab["title_2"])
            t3 = html_lib.escape(tab["title_3"])
            tab_contents.append(
                f'<div class="tab-content triple" id="{tab_id}" '
                f'style="display:{display};">'
                f'<div class="compare-wrapper">'
                f'<div class="compare-panel">'
                f'<div class="compare-label s1-label">{t1}</div>'
                f'<iframe src="{tab["src_1"]}" '
                f'style="width:100%;height:100%;border:none;" loading="lazy"></iframe>'
                f'</div>'
                f'<div class="compare-panel">'
                f'<div class="compare-label s2-label">{t2}</div>'
                f'<iframe src="{tab["src_2"]}" '
                f'style="width:100%;height:100%;border:none;" loading="lazy"></iframe>'
                f'</div>'
                f'<div class="compare-panel">'
                f'<div class="compare-label s3-label">{t3}</div>'
                f'<iframe src="{tab["src_3"]}" '
                f'style="width:100%;height:100%;border:none;" loading="lazy"></iframe>'
                f'</div>'
                f'</div>'
                f'</div>'
            )

    buttons_html = "\n".join(tab_buttons)
    contents_html = "\n".join(tab_contents)

    page = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Visualisasi Peta – Simulasi Kebijakan Jawa Timur</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: #f0f2f5;
    display: flex;
    flex-direction: column;
    height: 100vh;
  }}
  h1 {{
    text-align: center;
    padding: 14px 10px 8px;
    font-size: 20px;
    color: #1a1a2e;
    background: #ffffff;
    box-shadow: 0 1px 4px rgba(0,0,0,.1);
  }}
  .tab-bar {{
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 6px;
    padding: 10px 16px;
    background: #ffffff;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
  }}
  .tab-btn {{
    padding: 7px 14px;
    border: 1px solid #d0d0d0;
    border-radius: 20px;
    background: #f8f8f8;
    cursor: pointer;
    font-size: 13px;
    color: #444;
    transition: all .2s;
  }}
  .tab-btn:hover {{
    background: #e0e7ff;
    border-color: #7c83ff;
  }}
  .tab-btn.active {{
    background: #4361ee;
    color: #fff;
    border-color: #4361ee;
    font-weight: 600;
  }}
  .tab-content {{
    flex: 1;
    min-height: 0;
  }}
  .compare-wrapper {{
    display: flex;
    width: 100%;
    height: 100%;
    gap: 2px;
  }}
  .compare-panel {{
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }}
  .compare-label {{
    text-align: center;
    padding: 6px 8px;
    font-size: 13px;
    font-weight: 600;
    color: #1a1a2e;
    background: #e8eaf6;
    border-bottom: 2px solid #4361ee;
  }}
  .s1-label {{
    background: #fff3e0;
    border-bottom: 2px solid #f58518;
  }}
  .s2-label {{
    background: #e8f5e9;
    border-bottom: 2px solid #2ca02c;
  }}
  .s3-label {{
    background: #e8eaf6;
    border-bottom: 2px solid #4361ee;
  }}
  .compare-panel iframe {{
    flex: 1;
  }}
  .legend-bar {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 24px;
    padding: 8px 16px;
    background: #eef1ff;
    font-size: 12px;
    color: #333;
    border-bottom: 1px solid #d5d9f0;
    flex-wrap: wrap;
  }}
  .legend-item {{
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .legend-badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 11px;
    color: #fff;
  }}
  .legend-badge.s1 {{ background: #f58518; }}
  .legend-badge.s2 {{ background: #2ca02c; }}
  .legend-badge.s3 {{ background: #4361ee; }}
  .legend-badge.base {{ background: #6c757d; }}
</style>
</head>
<body>

<h1>Visualisasi Peta Interaktif &ndash; Simulasi Kebijakan Jawa Timur</h1>

<div class="legend-bar">
  <div class="legend-item">
    <span class="legend-badge base">Baseline</span>
    <span>Kondisi aktual tahun 2024</span>
  </div>
  <div class="legend-item">
    <span class="legend-badge s1">S1</span>
    <span>Belanja Daerah <b>+10%</b></span>
  </div>
  <div class="legend-item">
    <span class="legend-badge s2">S2</span>
    <span>PDRB per kapita <b>+5%</b></span>
  </div>
  <div class="legend-item">
    <span class="legend-badge s3">S3</span>
    <span>Belanja <b>+10%</b>, PAD <b>+10%</b>, PDRB <b>+5%</b></span>
  </div>
  <div class="legend-item">
    <span>&Delta;</span>
    <span>= Selisih (Skenario &minus; Baseline) &nbsp;|&nbsp; <b>Skala warna seragam</b> per indikator</span>
  </div>
</div>

<div class="tab-bar">
{buttons_html}
</div>

{contents_html}

<script>
function switchTab(idx) {{
  document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab_' + idx).style.display = 'block';
  document.getElementById('btn_' + idx).classList.add('active');
}}
</script>
</body>
</html>"""
    return page


# ─── Main ───────────────────────────────────────────────────────────
def main():
    # 1) Baca GeoJSON
    print("Membaca GeoJSON …")
    gdf = gpd.read_file(str(GEOJSON_PATH))
    gdf = harmonize_geojson(gdf)
    print(f"  → {len(gdf)} fitur terbaca.")

    # 2) Baca CSV simulasi
    print("Membaca CSV simulasi …")
    sim = pd.read_csv(str(CSV_PATH))
    print(f"  → {len(sim)} baris data simulasi.")

    # 3) Merge
    merged = gdf.merge(sim, on="nama_kabkota", how="left")

    unmatched = merged[merged["kode_kabkota"].isna()]
    if len(unmatched) > 0:
        print("⚠  Beberapa wilayah GeoJSON tidak cocok dengan CSV:")
        for _, row in unmatched.iterrows():
            print(f"    - {row['nama_kabkota']}")
    else:
        print("  ✓ Semua wilayah GeoJSON berhasil di-merge dengan CSV.")

    tabs_data = []

    # 4) Peta tunggal (Baseline saja)
    MAPS_DIR.mkdir(exist_ok=True)
    map_idx = 0

    for col, tab_label, title, cmap_name, fmt in SINGLE_INDICATORS:
        if col not in merged.columns:
            print(f"  ⚠ Kolom '{col}' tidak ditemukan – lewati.")
            continue
        print(f"Membuat peta: {tab_label} …")
        m = make_choropleth(merged, col, title, cmap_name=cmap_name, fmt=fmt)
        map_filename = f"maps/map_{map_idx}.html"
        (ROOT / map_filename).write_text(m.get_root().render(), encoding="utf-8")
        tabs_data.append({
            "label": tab_label,
            "type": "single",
            "src": map_filename,
        })
        map_idx += 1

    # 5) Triple comparison absolut S1 vs S2 vs S3 – shared color scale
    for col_s1, col_s2, col_s3, tab_label, t1, t2, t3, cmap_name, fmt in ABSOLUTE_TRIPLE:
        cols = [col_s1, col_s2, col_s3]
        if any(c not in merged.columns for c in cols):
            print(f"  ⚠ Kolom tidak ditemukan – lewati {tab_label}")
            continue
        print(f"Membuat peta perbandingan absolut: {tab_label} …")
        all_vals = pd.concat([merged[c] for c in cols]).dropna()
        shared_vmin, shared_vmax = float(all_vals.min()), float(all_vals.max())

        src_1 = f"maps/map_{map_idx}.html"
        src_2 = f"maps/map_{map_idx+1}.html"
        src_3 = f"maps/map_{map_idx+2}.html"
        for src, col, title in [(src_1, col_s1, t1), (src_2, col_s2, t2), (src_3, col_s3, t3)]:
            m = make_choropleth(merged, col, title, cmap_name=cmap_name, fmt=fmt,
                                vmin_override=shared_vmin, vmax_override=shared_vmax)
            (ROOT / src).write_text(m.get_root().render(), encoding="utf-8")
        map_idx += 3

        tabs_data.append({
            "label": tab_label,
            "type": "triple",
            "src_1": src_1, "src_2": src_2, "src_3": src_3,
            "title_1": t1, "title_2": t2, "title_3": t3,
        })

    # 6) Triple comparison delta S1 vs S2 vs S3 – shared color scale
    for col_s1, col_s2, col_s3, tab_label, t1, t2, t3, cmap_name, fmt in DELTA_TRIPLE:
        cols = [col_s1, col_s2, col_s3]
        if any(c not in merged.columns for c in cols):
            print(f"  ⚠ Kolom tidak ditemukan – lewati {tab_label}")
            continue
        print(f"Membuat peta perbandingan delta: {tab_label} …")
        all_vals = pd.concat([merged[c] for c in cols]).dropna()
        shared_vmin, shared_vmax = float(all_vals.min()), float(all_vals.max())

        src_1 = f"maps/map_{map_idx}.html"
        src_2 = f"maps/map_{map_idx+1}.html"
        src_3 = f"maps/map_{map_idx+2}.html"
        for src, col, title in [(src_1, col_s1, t1), (src_2, col_s2, t2), (src_3, col_s3, t3)]:
            m = make_choropleth(merged, col, title, cmap_name=cmap_name, fmt=fmt,
                                vmin_override=shared_vmin, vmax_override=shared_vmax)
            (ROOT / src).write_text(m.get_root().render(), encoding="utf-8")
        map_idx += 3

        tabs_data.append({
            "label": tab_label,
            "type": "triple",
            "src_1": src_1, "src_2": src_2, "src_3": src_3,
            "title_1": t1, "title_2": t2, "title_3": t3,
        })

    # 6) Gabungkan ke satu HTML
    print("Menggabungkan semua peta ke satu file HTML …")
    combined = build_combined_html(tabs_data)

    OUTPUT_PATH.write_text(combined, encoding="utf-8")
    print(f"  → Disimpan: {OUTPUT_PATH.name}")

    print(f"\nSelesai! Buka index.html di browser.\n"
          f"  → File peta tersimpan di: maps/ ({map_idx} file)")


if __name__ == "__main__":
    main()
