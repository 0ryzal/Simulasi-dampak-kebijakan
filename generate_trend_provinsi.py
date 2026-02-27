"""
Visualisasi Trend TPT, IPM, dan Realisasi PAD 2020–2024
Tingkat Provinsi Jawa Timur (agregat dari seluruh kab/kota)
========================================================
Output:
  maps_png/trend_provinsi.png   – grafik statis (PNG)
  maps/trend_provinsi.html      – grafik interaktif (Plotly)
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
import numpy as np
import json

ROOT = Path(".").resolve()
YEARS = [2020, 2021, 2022, 2023, 2024]
OUT_PNG = ROOT / "maps_png" / "trend_provinsi.png"
OUT_HTML = ROOT / "maps" / "trend_provinsi.html"

# ─── 1. Baca TPT per tahun → nilai provinsi Jawa Timur ──────────────
def read_tpt(year: int) -> float:
    path = ROOT / "TPT" / f"tpt {year}.xlsx"
    df = pd.read_excel(path, header=None, skiprows=2)
    df.columns = ["nama", "nilai"]
    df["nama"] = df["nama"].astype(str).str.strip()
    df["nilai"] = pd.to_numeric(df["nilai"], errors="coerce")
    # Gunakan baris "Jawa Timur" sebagai nilai provinsi
    mask = df["nama"].str.lower().str.contains("jawa timur", na=False)
    if mask.any():
        return float(df.loc[mask, "nilai"].values[0])
    # Fallback: rata-rata 38 kab/kota (skip baris tahun & total)
    valid = df[df["nama"].str.startswith(("Kabupaten", "Kota"), na=False)]
    return float(valid["nilai"].mean())

# ─── 2. Baca IPM per tahun → nilai provinsi Jawa Timur ──────────────
def read_ipm(year: int) -> float:
    path = ROOT / "IPM" / f"ipm {year}.xlsx"
    df = pd.read_excel(path, header=None, skiprows=2)
    df.columns = ["nama", "nilai"]
    df["nama"] = df["nama"].astype(str).str.strip()
    df["nilai"] = pd.to_numeric(df["nilai"], errors="coerce")
    mask = df["nama"].str.lower().str.contains("jawa timur", na=False)
    if mask.any():
        return float(df.loc[mask, "nilai"].values[0])
    valid = df[df["nama"].str.startswith(("Kabupaten", "Kota"), na=False)]
    return float(valid["nilai"].mean())

# ─── 3. Baca PAD per tahun → total realisasi PAD seluruh kab/kota ───
def read_pad_total(year: int) -> float:
    pad_root = ROOT / "pad"
    total = 0.0
    for kab_dir in sorted(pad_root.iterdir()):
        if not kab_dir.is_dir():
            continue
        # Cari file yang cocok dengan tahun
        matches = list(kab_dir.glob(f"*{year}*.xlsx"))
        if not matches:
            continue
        df = pd.read_excel(matches[0])
        df.columns = [str(c).strip() for c in df.columns]
        # Cari baris PAD (bukan Pendapatan Daerah)
        real_col = [c for c in df.columns if "reali" in c.lower()]
        akun_col = [c for c in df.columns if "akun" in c.lower()]
        if not real_col or not akun_col:
            continue
        mask = df[akun_col[0]].astype(str).str.strip().str.upper() == "PAD"
        if mask.any():
            val = pd.to_numeric(df.loc[mask, real_col[0]].values[0], errors="coerce")
            if pd.notna(val):
                total += val
    return total

# ─── Kumpulkan data ───────────────────────────────────────────────────
print("Mengumpulkan data TPT, IPM, PAD 2020–2024 …")
tpt_vals, ipm_vals, pad_vals = [], [], []
for y in YEARS:
    t = read_tpt(y); tpt_vals.append(t)
    i = read_ipm(y); ipm_vals.append(i)
    p = read_pad_total(y); pad_vals.append(p)
    print(f"  {y}: TPT={t:.2f}%  IPM={i:.2f}  PAD=Rp {p/1e12:.2f}T")

pad_T = [p / 1e12 for p in pad_vals]   # konversi ke Triliun

# ─── 4a. PNG – kombinasi 3 panel ─────────────────────────────────────
print("\nMembuat PNG …")
fig = plt.figure(figsize=(18, 6))
fig.suptitle(
    "Trend TPT, IPM, dan Realisasi PAD Provinsi Jawa Timur 2020–2024",
    fontsize=15, fontweight="bold", y=1.02,
)
gs = gridspec.GridSpec(1, 3, figure=fig, wspace=0.38)

PALETTE = {"tpt": "#e05c3a", "ipm": "#2ca02c", "pad": "#4361ee"}
MARKER = "o"

def plot_trend(ax, x, y, color, ylabel, title, fmt=".2f", unit=""):
    ax.plot(x, y, color=color, linewidth=2.5, marker=MARKER,
            markersize=7, markerfacecolor="white", markeredgewidth=2)
    for xi, yi in zip(x, y):
        ax.annotate(f"{yi:{fmt}}{unit}", (xi, yi),
                    textcoords="offset points", xytext=(0, 10),
                    ha="center", fontsize=9.5, fontweight="bold", color=color)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=8)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_xticks(x)
    ax.set_xlim(x[0] - 0.4, x[-1] + 0.4)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter(f"%{fmt}"))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    # Warnai area bawah kurva
    ax.fill_between(x, y, min(y) - (max(y)-min(y))*0.15,
                    alpha=0.08, color=color)

ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])
ax3 = fig.add_subplot(gs[2])

plot_trend(ax1, YEARS, tpt_vals, PALETTE["tpt"],
           "TPT (%)", "Tingkat Pengangguran Terbuka (TPT)", ".2f", "%")
plot_trend(ax2, YEARS, ipm_vals, PALETTE["ipm"],
           "Nilai IPM", "Indeks Pembangunan Manusia (IPM)", ".2f")
plot_trend(ax3, YEARS, pad_T, PALETTE["pad"],
           "Realisasi PAD (Triliun Rp)", "Realisasi PAD", ".2f", "T")

# Anotasi sumber
fig.text(0.5, -0.04,
         "Sumber: BPS & APBD Kab/Kota Jawa Timur 2020–2024  |  TPT & IPM: nilai agregat provinsi, PAD: total realisasi kab/kota",
         ha="center", fontsize=9, color="#666")

plt.tight_layout()
fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  ✓ Saved: {OUT_PNG.name}")

# ─── 4b. HTML interaktif – Plotly ────────────────────────────────────
print("Membuat HTML interaktif (Plotly) …")
plotly_html = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trend Provinsi Jawa Timur 2020–2024</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Segoe UI',sans-serif; background:#f4f6fb; padding:20px; }}
  h2 {{ text-align:center; color:#1a1a2e; margin-bottom:6px; font-size:17px; }}
  p.sub {{ text-align:center; color:#666; font-size:12px; margin-bottom:20px; }}
  .charts {{ display:flex; flex-direction:column; gap:16px; }}
  .chart-box {{
    background:#fff; border-radius:10px;
    box-shadow:0 2px 8px rgba(0,0,0,.1); padding:12px;
  }}
  .note {{ text-align:center; font-size:11px; color:#888; margin-top:16px; }}
</style>
</head>
<body>
<h2>Trend TPT, IPM, dan Realisasi PAD &ndash; Provinsi Jawa Timur 2020–2024</h2>
<p class="sub">TPT &amp; IPM: nilai agregat provinsi &bull; Total Realisasi PAD se-Jawa Timur</p>
<div class="charts">
  <div class="chart-box"><div id="chart-tpt"></div></div>
  <div class="chart-box"><div id="chart-ipm"></div></div>
  <div class="chart-box"><div id="chart-pad"></div></div>
</div>
<p class="note">Sumber: BPS &amp; APBD Kab/Kota Jawa Timur 2020–2024</p>
<script>
const years = {json.dumps(YEARS)};
const tpt   = {json.dumps([round(v,3) for v in tpt_vals])};
const ipm   = {json.dumps([round(v,3) for v in ipm_vals])};
const pad   = {json.dumps([round(v,2) for v in pad_T])};

const layout_base = {{
  height: 280,
  margin: {{l:60, r:30, t:40, b:40}},
  plot_bgcolor: "#f9faff",
  paper_bgcolor: "transparent",
  font: {{family:"Segoe UI,sans-serif", size:12}},
  xaxis: {{tickvals: years, ticktext: years.map(String), gridcolor:"#ececec"}},
  hovermode: "x unified",
}};

const line_base = {{
  type:"scatter", mode:"lines+markers+text",
  line:{{width:3}}, marker:{{size:8, symbol:"circle"}},
  textposition:"top center",
  textfont:{{size:12, color:"inherit"}},
}};

Plotly.newPlot("chart-tpt", [{{
  ...line_base, x:years, y:tpt,
  name:"TPT (%)",
  text: tpt.map(v => v.toFixed(2)+"%"),
  line:{{color:"#e05c3a", width:3}},
  marker:{{color:"#e05c3a", size:9, line:{{color:"white",width:2}}}},
  fill:"tozeroy", fillcolor:"rgba(224,92,58,0.07)",
  hovertemplate:"%{{x}} &bull; TPT: %{{y:.2f}}%<extra></extra>",
}}], {{...layout_base, title:"Tingkat Pengangguran Terbuka (TPT) — Rata-rata Jawa Timur",
  yaxis:{{title:"TPT (%)", gridcolor:"#ececec", rangemode:"tozero"}}}}, {{responsive:true}});

Plotly.newPlot("chart-ipm", [{{
  ...line_base, x:years, y:ipm,
  name:"IPM",
  text: ipm.map(v => v.toFixed(2)),
  line:{{color:"#2ca02c", width:3}},
  marker:{{color:"#2ca02c", size:9, line:{{color:"white",width:2}}}},
  fill:"tozeroy", fillcolor:"rgba(44,160,44,0.07)",
  hovertemplate:"%{{x}} &bull; IPM: %{{y:.2f}}<extra></extra>",
}}], {{...layout_base, title:"Indeks Pembangunan Manusia (IPM) — Rata-rata Jawa Timur",
  yaxis:{{title:"Nilai IPM", gridcolor:"#ececec"}}}}, {{responsive:true}});

Plotly.newPlot("chart-pad", [{{
  ...line_base, x:years, y:pad,
  name:"PAD (Triliun Rp)",
  text: pad.map(v => "Rp "+v.toFixed(2)+"T"),
  line:{{color:"#4361ee", width:3}},
  marker:{{color:"#4361ee", size:9, line:{{color:"white",width:2}}}},
  fill:"tozeroy", fillcolor:"rgba(67,97,238,0.07)",
  hovertemplate:"%{{x}} &bull; PAD: Rp %{{y:.2f}}T<extra></extra>",
}}], {{...layout_base, title:"Total Realisasi PAD Seluruh Kab/Kota Jawa Timur",
  yaxis:{{title:"Realisasi PAD (Triliun Rp)", gridcolor:"#ececec"}}}}, {{responsive:true}});
</script>
</body>
</html>"""

OUT_HTML.write_text(plotly_html, encoding="utf-8")
print(f"  ✓ Saved: {OUT_HTML.name}")
print("\n✅ Selesai!")
