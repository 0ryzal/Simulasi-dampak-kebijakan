"""
Generate PNG Choropleth Maps – Simulasi Kebijakan S1, S2, S3
=============================================================
Script ini membaca:
  1. File GeoJSON kabupaten/kota Jawa Timur
  2. File CSV hasil simulasi kebijakan (policy_simulation_output.csv)

Kemudian menghasilkan file PNG peta choropleth untuk setiap skenario:
  - choropleth_s1.png  (Δ Kemiskinan, Δ IPM, Δ TPT untuk S1)
  - choropleth_s2.png  (Δ Kemiskinan, Δ IPM, Δ TPT untuk S2)
  - choropleth_s3.png  (Δ Kemiskinan, Δ IPM, Δ TPT untuk S3)

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


# ─── Konfigurasi ────────────────────────────────────────────────────
ROOT = Path(".").resolve()
GEOJSON_PATH = ROOT / "Kabupaten-Kota (Provinsi Jawa Timur).geojson"
CSV_PATH = ROOT / "policy_simulation_output.csv"


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


# ─── Main ───────────────────────────────────────────────────────────
def main():
    # 1) Baca GeoJSON
    print("Membaca GeoJSON …")
    gdf_raw = gpd.read_file(str(GEOJSON_PATH))
    print(f"  → {len(gdf_raw)} fitur terbaca.")

    # Build join key from GeoJSON
    if {"NAME_2", "TYPE_2"}.issubset(gdf_raw.columns):
        gdf_raw["join_name"] = gdf_raw.apply(_build_geo_key, axis=1)
    else:
        name_col = [c for c in gdf_raw.columns if c != "geometry"][0]
        gdf_raw["join_name"] = gdf_raw[name_col].apply(_norm)

    # 2) Baca CSV simulasi
    print("Membaca CSV simulasi …")
    output = pd.read_csv(str(CSV_PATH))
    print(f"  → {len(output)} baris data simulasi.")

    out = output.copy()
    out["join_name"] = out["nama_kabkota"].apply(_norm)

    # 3) Columns to merge
    merge_cols = (
        ["join_name"] +
        [f"delta_poor_rate_s{i}" for i in (1, 2, 3)] +
        [f"delta_IPM_s{i}" for i in (1, 2, 3)] +
        [f"delta_TPT_s{i}" for i in (1, 2, 3)] +
        # Also merge absolute values for S1, S2, S3 and baseline
        ["nama_kabkota"] +
        [f"poor_rate_s{i}" for i in (1, 2, 3)] +
        [f"IPM_s{i}" for i in (1, 2, 3)] +
        [f"TPT_s{i}" for i in (1, 2, 3)] +
        ["poor_rate_baseline", "IPM_baseline", "TPT_baseline"]
    )
    # Filter to existing columns
    merge_cols = [c for c in merge_cols if c in out.columns]

    gdf_base = gdf_raw.merge(out[merge_cols], on="join_name", how="left")

    matched = gdf_base["delta_poor_rate_s1"].notna().sum()
    print(f"  Wilayah tercocokkan: {matched}/{len(gdf_base)}")
    if matched < len(gdf_base):
        unmatched = gdf_base[gdf_base["delta_poor_rate_s1"].isna()]["join_name"].tolist()
        print("  Tidak cocok:", unmatched)
    else:
        print("  ✓ Semua wilayah berhasil di-merge.")

    # ═══════════════════════════════════════════════════════════════
    # 4) PETA DELTA per Skenario (3 panel: ΔKemiskinan, ΔIPM, ΔTPT)
    # ═══════════════════════════════════════════════════════════════
    scenarios = {
        "S1 – Belanja Daerah +10%": 1,
        "S2 – PDRB per Kapita +5%": 2,
        "S3 – Belanja +10%, PAD +10%, PDRB +5%": 3,
    }

    indicator_specs = [
        ("delta_poor_rate_s{n}", "Δ Kemiskinan (per 1000)", "RdYlGn_r"),
        ("delta_IPM_s{n}",       "Δ IPM (poin)",            "RdYlGn"),
        ("delta_TPT_s{n}",       "Δ TPT (pp)",              "RdYlGn_r"),
    ]

    for s_label, s_num in scenarios.items():
        fig, axes = plt.subplots(1, 3, figsize=(20, 7))
        fig.suptitle(
            f"Peta Dampak Simulasi: {s_label}",
            fontsize=15, fontweight="bold", y=1.01,
        )

        for ax, (col_tpl, ind_title, cmap) in zip(axes, indicator_specs):
            col = col_tpl.replace("{n}", str(s_num))
            valid = gdf_base[col].dropna()
            vmin = float(valid.quantile(0.05)) if len(valid) else None
            vmax = float(valid.quantile(0.95)) if len(valid) else None

            gdf_base.plot(
                column=col,
                cmap=cmap,
                linewidth=0.3,
                edgecolor="black",
                legend=True,
                vmin=vmin,
                vmax=vmax,
                legend_kwds={"shrink": 0.6, "label": ind_title},
                missing_kwds={"color": "lightgrey", "label": "NA"},
                ax=ax,
            )
            # Centroid value labels
            for _, row in gdf_base.iterrows():
                if pd.notna(row.get(col)):
                    cx, cy = row.geometry.centroid.x, row.geometry.centroid.y
                    ax.text(
                        cx, cy, f"{row[col]:.2f}", fontsize=4.5,
                        ha="center", va="center", color="black",
                    )

            ax.set_title(ind_title, fontsize=11)
            ax.set_axis_off()

        plt.tight_layout()
        fname = f"choropleth_s{s_num}.png"
        plt.savefig(fname, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  ✓ Saved: {fname}")

    # ═══════════════════════════════════════════════════════════════
    # 5) PETA ABSOLUT per Skenario (Kemiskinan, IPM, TPT)
    # ═══════════════════════════════════════════════════════════════
    abs_indicator_specs = [
        ("poor_rate_s{n}", "Kemiskinan (per 1000 penduduk)", "YlOrRd"),
        ("IPM_s{n}",       "IPM",                            "YlGn"),
        ("TPT_s{n}",       "TPT (%)",                        "PuBu"),
    ]

    for s_label, s_num in scenarios.items():
        fig, axes = plt.subplots(1, 3, figsize=(20, 7))
        fig.suptitle(
            f"Peta Indikator Absolut: {s_label}",
            fontsize=15, fontweight="bold", y=1.01,
        )

        for ax, (col_tpl, ind_title, cmap) in zip(axes, abs_indicator_specs):
            col = col_tpl.replace("{n}", str(s_num))
            if col not in gdf_base.columns:
                ax.set_visible(False)
                continue

            valid = gdf_base[col].dropna()
            vmin = float(valid.quantile(0.05)) if len(valid) else None
            vmax = float(valid.quantile(0.95)) if len(valid) else None

            gdf_base.plot(
                column=col,
                cmap=cmap,
                linewidth=0.3,
                edgecolor="black",
                legend=True,
                vmin=vmin,
                vmax=vmax,
                legend_kwds={"shrink": 0.6, "label": ind_title},
                missing_kwds={"color": "lightgrey", "label": "NA"},
                ax=ax,
            )
            for _, row in gdf_base.iterrows():
                if pd.notna(row.get(col)):
                    cx, cy = row.geometry.centroid.x, row.geometry.centroid.y
                    ax.text(
                        cx, cy, f"{row[col]:.1f}", fontsize=4.5,
                        ha="center", va="center", color="black",
                    )

            ax.set_title(f"{ind_title} – {s_label}", fontsize=10)
            ax.set_axis_off()

        plt.tight_layout()
        fname = f"map_absolut_s{s_num}.png"
        plt.savefig(fname, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  ✓ Saved: {fname}")

    # ═══════════════════════════════════════════════════════════════
    # 6) PETA SKENARIO TERBAIK per Daerah
    # ═══════════════════════════════════════════════════════════════
    def minmax_global(series, global_min, global_max):
        rng = global_max - global_min
        return (series - global_min) / rng if rng != 0 else pd.Series(0.5, index=series.index)

    df = output.copy()
    df["join_name"] = df["nama_kabkota"].apply(_norm)

    poor_all = pd.concat([df[f"delta_poor_rate_s{s}"] for s in (1, 2, 3)])
    ipm_all  = pd.concat([df[f"delta_IPM_s{s}"]       for s in (1, 2, 3)])
    tpt_all  = pd.concat([df[f"delta_TPT_s{s}"]       for s in (1, 2, 3)])

    poor_min, poor_max = poor_all.min(), poor_all.max()
    ipm_min,  ipm_max  = ipm_all.min(),  ipm_all.max()
    tpt_min,  tpt_max  = tpt_all.min(),  tpt_all.max()

    scores = pd.DataFrame(index=df.index)
    for s in (1, 2, 3):
        norm_poor = 1 - minmax_global(df[f"delta_poor_rate_s{s}"], poor_min, poor_max)
        norm_ipm  =     minmax_global(df[f"delta_IPM_s{s}"],       ipm_min,  ipm_max)
        norm_tpt  = 1 - minmax_global(df[f"delta_TPT_s{s}"],       tpt_min,  tpt_max)
        scores[f"score_s{s}"] = (norm_poor + norm_ipm + norm_tpt) / 3

    df["best_scenario"] = scores.idxmax(axis=1).str.replace("score_s", "S").astype(str)
    df["best_score"] = scores.max(axis=1)

    print("\n  Distribusi skenario terbaik:")
    print(df["best_scenario"].value_counts().to_string())

    gdf_best = gdf_raw.merge(
        df[["join_name", "best_scenario", "best_score"]],
        on="join_name", how="left",
    )

    scen_colors = {"S1": "#3498db", "S2": "#e67e22", "S3": "#2ecc71"}
    gdf_best["_color"] = gdf_best["best_scenario"].map(scen_colors).fillna("#cccccc")

    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    gdf_best.plot(color=gdf_best["_color"], linewidth=0.3, edgecolor="black", ax=ax)

    for _, row in gdf_best.iterrows():
        if pd.notna(row.get("best_scenario")) and pd.notna(row.get("best_score")):
            cx, cy = row.geometry.centroid.x, row.geometry.centroid.y
            ax.text(
                cx, cy, row["best_scenario"], fontsize=4.8,
                ha="center", va="center", color="black", fontweight="bold",
            )

    legend_patches = [mpatches.Patch(color=c, label=f"Skenario {s}") for s, c in scen_colors.items()]
    legend_patches.append(mpatches.Patch(color="#cccccc", label="Data NA"))
    ax.legend(
        handles=legend_patches, fontsize=10, loc="lower left",
        title="Skenario Terbaik", title_fontsize=10,
    )
    ax.set_title(
        "Skenario Terbaik per Daerah\n(Berdasarkan Skor Komposit: Δ Kemiskinan + Δ IPM + Δ TPT)",
        fontsize=14, fontweight="bold",
    )
    ax.set_axis_off()
    plt.tight_layout()
    plt.savefig("choropleth_best_scenario.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✓ Saved: choropleth_best_scenario.png")

    # ═══════════════════════════════════════════════════════════════
    # 7) PETA SKOR KOMPOSIT
    # ═══════════════════════════════════════════════════════════════
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    valid = gdf_best["best_score"].dropna()
    gdf_best.plot(
        column="best_score",
        cmap="YlGnBu",
        linewidth=0.3,
        edgecolor="black",
        legend=True,
        vmin=float(valid.quantile(0.05)) if len(valid) else None,
        vmax=float(valid.quantile(0.95)) if len(valid) else None,
        legend_kwds={"label": "Skor Komposit (0–1)", "shrink": 0.6},
        missing_kwds={"color": "lightgrey", "label": "NA"},
        ax=ax,
    )
    for _, row in gdf_best.iterrows():
        if pd.notna(row.get("best_score")):
            cx, cy = row.geometry.centroid.x, row.geometry.centroid.y
            ax.text(
                cx, cy, f"{row['best_score']:.2f}", fontsize=4.5,
                ha="center", va="center", color="black",
            )

    ax.set_title("Skor Komposit Skenario Terbaik per Daerah", fontsize=14, fontweight="bold")
    ax.set_axis_off()
    plt.tight_layout()
    plt.savefig("choropleth_best_score.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✓ Saved: choropleth_best_score.png")

    print("\n✅ Selesai! Semua peta PNG berhasil dibuat.")


if __name__ == "__main__":
    main()
