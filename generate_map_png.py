"""
Generate PNG Choropleth Maps – Simulasi Kebijakan S1, S2, S3
=============================================================
Script ini membaca:
  1. File GeoJSON kabupaten/kota Jawa Timur
  2. File CSV hasil simulasi kebijakan (policy_simulation_output.csv)

Output (folder maps_png/):
  comparison_delta.png    – grid 3×3: Δ Kemiskinan/IPM/TPT vs S1/S2/S3 (shared scale per baris)
  comparison_absolut.png  – grid 3×3: nilai absolut per indikator (shared scale per baris)
  best_scenario.png       – peta skenario terbaik per daerah
  best_score.png          – peta skor komposit

Skenario:
  S1 – Belanja Daerah +10%
  S2 – PDRB per Kapita +5%
  S3 – Belanja +10%, PAD +10%, PDRB +5% (Gabungan)
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import matplotlib.cm as mcm
from matplotlib.colorbar import ColorbarBase


# ─── Konfigurasi ────────────────────────────────────────────────────
ROOT = Path(".").resolve()
GEOJSON_PATH = ROOT / "Kabupaten-Kota (Provinsi Jawa Timur).geojson"
CSV_PATH = ROOT / "policy_simulation_output.csv"
OUT_DIR = ROOT / "maps_png"
OUT_DIR.mkdir(exist_ok=True)

S_COLORS = {"S1": "#f58518", "S2": "#2ca02c", "S3": "#4361ee"}
S_LABELS = {
    "S1": "S1 – Belanja +10%",
    "S2": "S2 – PDRB +5%",
    "S3": "S3 – Belanja +10%, PAD +10%, PDRB +5%",
}


# ─── Fungsi bantu: normalisasi nama ─────────────────────────────────
def _norm(x):
    s = "" if pd.isna(x) else str(x).strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^kab\.?\s+", "kabupaten ", s)
    s = re.sub(r"^kota\.?\s+", "kota ", s)
    return s


def _build_geo_key(row):
    t = str(row["TYPE_2"]).strip()
    n = re.sub(
        r"^(?:Kabupaten|Kota)\s+", "",
        str(row["NAME_2"]).strip(),
        flags=re.IGNORECASE,
    )
    return _norm(f"{t} {n}")


# ─── Fungsi: plot satu choropleth panel ─────────────────────────────
def plot_panel(ax, gdf, col, cmap, vmin, vmax, fmt=".2f", fontsize=4.5):
    """Plot choropleth ke axes dengan shared vmin/vmax."""
    gdf.plot(
        column=col,
        cmap=cmap,
        linewidth=0.4,
        edgecolor="#444444",
        legend=False,
        vmin=vmin,
        vmax=vmax,
        missing_kwds={"color": "#dddddd", "label": "NA"},
        ax=ax,
    )
    for _, row in gdf.iterrows():
        val = row.get(col)
        if pd.notna(val):
            cx, cy = row.geometry.centroid.x, row.geometry.centroid.y
            ax.text(cx, cy, f"{val:{fmt}}", fontsize=fontsize,
                    ha="center", va="center", color="black")
    ax.set_axis_off()


def add_shared_colorbar(fig, axes_row, cmap, vmin, vmax, label):
    """Tambah satu colorbar di kanan baris axes."""
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    sm = mcm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes_row, shrink=0.7, pad=0.01, aspect=20)
    cbar.set_label(label, fontsize=9)
    cbar.ax.tick_params(labelsize=8)


# ─── Main ───────────────────────────────────────────────────────────
def main():
    # 1) Baca GeoJSON
    print("Membaca GeoJSON …")
    gdf_raw = gpd.read_file(str(GEOJSON_PATH))
    print(f"  → {len(gdf_raw)} fitur terbaca.")

    if {"NAME_2", "TYPE_2"}.issubset(gdf_raw.columns):
        gdf_raw["join_name"] = gdf_raw.apply(_build_geo_key, axis=1)
    else:
        name_col = [c for c in gdf_raw.columns if c != "geometry"][0]
        gdf_raw["join_name"] = gdf_raw[name_col].apply(_norm)

    # 2) Baca CSV simulasi
    print("Membaca CSV simulasi …")
    output = pd.read_csv(str(CSV_PATH))
    out = output.copy()
    out["join_name"] = out["nama_kabkota"].apply(_norm)

    merge_cols = [c for c in out.columns if c != "nama_kabkota"] + ["nama_kabkota"]
    gdf = gdf_raw.merge(out[merge_cols], on="join_name", how="left")

    matched = gdf["delta_poor_rate_s1"].notna().sum()
    print(f"  Wilayah tercocokkan: {matched}/{len(gdf)}")
    if matched == len(gdf):
        print("  ✓ Semua wilayah berhasil di-merge.")

    # ══════════════════════════════════════════════════════════════
    # 3) PERBANDINGAN DELTA – grid 3 baris (indikator) × 3 kolom (S)
    #    shared color scale per baris
    # ══════════════════════════════════════════════════════════════
    delta_specs = [
        ("delta_poor_rate_s{n}", "RdYlGn_r", "Δ Kemiskinan (per 1.000 pddk)", ".3f"),
        ("delta_IPM_s{n}",       "RdYlGn",   "Δ IPM (poin)",                  ".3f"),
        ("delta_TPT_s{n}",       "RdYlGn_r", "Δ TPT (pp)",                    ".3f"),
    ]

    fig, axes = plt.subplots(3, 3, figsize=(22, 18))
    fig.suptitle(
        "Perbandingan Dampak Kebijakan: Δ Indikator (S1 vs S2 vs S3)\n"
        "Skala warna seragam per indikator agar dapat dibandingkan langsung",
        fontsize=14, fontweight="bold", y=1.01,
    )

    # Header kolom
    for j, s in enumerate(["S1", "S2", "S3"]):
        axes[0, j].set_title(S_LABELS[s], fontsize=11, fontweight="bold",
                             color=S_COLORS[s], pad=8)

    for i, (col_tpl, cmap, label, fmt) in enumerate(delta_specs):
        cols = [col_tpl.replace("{n}", str(n)) for n in (1, 2, 3)]
        all_vals = pd.concat([gdf[c].dropna() for c in cols])
        vmin = float(all_vals.quantile(0.02))
        vmax = float(all_vals.quantile(0.98))

        for j, (col, s) in enumerate(zip(cols, ["S1", "S2", "S3"])):
            plot_panel(axes[i, j], gdf, col, cmap, vmin, vmax, fmt=fmt)

        # Label baris di kiri
        axes[i, 0].set_ylabel(label, fontsize=11, labelpad=10, rotation=90)
        add_shared_colorbar(fig, axes[i, :], cmap, vmin, vmax, label)

    plt.tight_layout()
    out_path = OUT_DIR / "comparison_delta.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Saved: {out_path.name}")

    # ══════════════════════════════════════════════════════════════
    # 4) PERBANDINGAN ABSOLUT – grid 3 × 3, shared scale per baris
    # ══════════════════════════════════════════════════════════════
    abs_specs = [
        ("poor_rate_s{n}", "YlOrRd", "Kemiskinan (per 1.000 pddk)", ".1f"),
        ("IPM_s{n}",       "YlGn",   "IPM",                          ".2f"),
        ("TPT_s{n}",       "PuBu",   "TPT (%)",                      ".2f"),
    ]

    fig, axes = plt.subplots(3, 3, figsize=(22, 18))
    fig.suptitle(
        "Perbandingan Nilai Absolut Indikator: S1 vs S2 vs S3\n"
        "Skala warna seragam per indikator",
        fontsize=14, fontweight="bold", y=1.01,
    )

    for j, s in enumerate(["S1", "S2", "S3"]):
        axes[0, j].set_title(S_LABELS[s], fontsize=11, fontweight="bold",
                             color=S_COLORS[s], pad=8)

    for i, (col_tpl, cmap, label, fmt) in enumerate(abs_specs):
        cols = [col_tpl.replace("{n}", str(n)) for n in (1, 2, 3)]
        all_vals = pd.concat([gdf[c].dropna() for c in cols if c in gdf.columns])
        vmin = float(all_vals.quantile(0.02))
        vmax = float(all_vals.quantile(0.98))

        for j, (col, s) in enumerate(zip(cols, ["S1", "S2", "S3"])):
            if col in gdf.columns:
                plot_panel(axes[i, j], gdf, col, cmap, vmin, vmax, fmt=fmt)
            else:
                axes[i, j].set_axis_off()

        axes[i, 0].set_ylabel(label, fontsize=11, labelpad=10, rotation=90)
        add_shared_colorbar(fig, axes[i, :], cmap, vmin, vmax, label)

    plt.tight_layout()
    out_path = OUT_DIR / "comparison_absolut.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Saved: {out_path.name}")

    # ══════════════════════════════════════════════════════════════
    # 5) PETA SKENARIO TERBAIK per Daerah (skor komposit)
    # ══════════════════════════════════════════════════════════════
    def minmax_global(series, global_min, global_max):
        rng = global_max - global_min
        return (series - global_min) / rng if rng != 0 else pd.Series(0.5, index=series.index)

    df = output.copy()
    df["join_name"] = df["nama_kabkota"].apply(_norm)

    poor_all = pd.concat([df[f"delta_poor_rate_s{s}"] for s in (1, 2, 3)])
    ipm_all  = pd.concat([df[f"delta_IPM_s{s}"]       for s in (1, 2, 3)])
    tpt_all  = pd.concat([df[f"delta_TPT_s{s}"]       for s in (1, 2, 3)])

    scores = pd.DataFrame(index=df.index)
    for s in (1, 2, 3):
        norm_poor = 1 - minmax_global(df[f"delta_poor_rate_s{s}"], poor_all.min(), poor_all.max())
        norm_ipm  =     minmax_global(df[f"delta_IPM_s{s}"],       ipm_all.min(),  ipm_all.max())
        norm_tpt  = 1 - minmax_global(df[f"delta_TPT_s{s}"],       tpt_all.min(),  tpt_all.max())
        scores[f"score_s{s}"] = (norm_poor + norm_ipm + norm_tpt) / 3

    df["best_scenario"] = scores.idxmax(axis=1).str.replace("score_s", "S")
    df["best_score"]    = scores.max(axis=1)

    print("\n  Distribusi skenario terbaik:")
    print(df["best_scenario"].value_counts().to_string())

    gdf_best = gdf_raw.merge(df[["join_name", "best_scenario", "best_score"]], on="join_name", how="left")
    gdf_best["_color"] = gdf_best["best_scenario"].map(S_COLORS).fillna("#cccccc")

    # Panel kiri: skenario terbaik | Panel kanan: skor komposit
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(22, 9))
    fig.suptitle(
        "Skenario Terbaik & Skor Komposit per Daerah\n"
        "(Skor = rata-rata Δ Kemiskinan ↓ + Δ IPM ↑ + Δ TPT ↓, dinormalisasi 0–1)",
        fontsize=13, fontweight="bold",
    )

    # Kiri: warna per skenario
    gdf_best.plot(color=gdf_best["_color"], linewidth=0.4, edgecolor="#333333", ax=ax1)
    for _, row in gdf_best.iterrows():
        if pd.notna(row.get("best_scenario")):
            cx, cy = row.geometry.centroid.x, row.geometry.centroid.y
            ax1.text(cx, cy, row["best_scenario"], fontsize=5, ha="center", va="center",
                     fontweight="bold", color="black")
    legend_patches = [mpatches.Patch(color=S_COLORS[s], label=S_LABELS[s]) for s in ("S1", "S2", "S3")]
    legend_patches.append(mpatches.Patch(color="#cccccc", label="Data NA"))
    ax1.legend(handles=legend_patches, fontsize=9, loc="lower left",
               title="Skenario Terbaik", title_fontsize=9)
    ax1.set_title("Skenario Terbaik per Daerah", fontsize=12, fontweight="bold")
    ax1.set_axis_off()

    # Kanan: skor komposit heatmap
    valid = gdf_best["best_score"].dropna()
    gdf_best.plot(
        column="best_score", cmap="YlGnBu",
        linewidth=0.4, edgecolor="#333333",
        legend=True,
        vmin=float(valid.quantile(0.05)), vmax=float(valid.quantile(0.95)),
        legend_kwds={"label": "Skor Komposit (0–1)", "shrink": 0.7},
        missing_kwds={"color": "#dddddd", "label": "NA"},
        ax=ax2,
    )
    for _, row in gdf_best.iterrows():
        if pd.notna(row.get("best_score")) and pd.notna(row.get("best_scenario")):
            cx, cy = row.geometry.centroid.x, row.geometry.centroid.y
            ax2.text(cx, cy, f"{row['best_score']:.2f}", fontsize=4.5,
                     ha="center", va="center", color="black")
    ax2.set_title("Skor Komposit per Daerah", fontsize=12, fontweight="bold")
    ax2.set_axis_off()

    plt.tight_layout()
    out_path = OUT_DIR / "best_scenario.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Saved: {out_path.name}")

    print(f"\n✅ Selesai! Semua PNG tersimpan di folder: maps_png/")


if __name__ == "__main__":
    main()

