"""
analysis_x6.py — X6: Campaign density delta across all four sources.

Question: Which extractor's record counts drive the C2 39% density delta
over C1? Or is the delta CC-specific?

Scope: 140 episodes (full corpus).
Per-source records-per-episode computed over covered episodes (episodes
where that source has ≥1 record).
"""

import csv
import os
import sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x_utils

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

SOURCES = ["EC", "TM", "LR", "CC"]


def run():
    all_records = x_utils.load_unified_records()

    # Group by episode and source
    by_ep_src: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    ep_campaigns: dict[str, str] = {}
    for r in all_records:
        ep = r["episode_combined"]
        by_ep_src[ep][r["source"]].append(r)
        ep_campaigns[ep] = r["campaign"]

    all_eps = sorted(by_ep_src.keys())
    print(f"X6 scope: {len(all_eps)} episodes (full corpus)")

    # Per-source: count records and covered episodes by campaign
    source_stats: dict[str, dict] = {}
    for src in SOURCES:
        c1_recs = c2_recs = 0
        c1_eps = c2_eps = 0
        for ep in all_eps:
            camp = ep_campaigns[ep]
            n = len(by_ep_src[ep].get(src, []))
            if n == 0:
                continue
            if camp == "C1":
                c1_recs += n
                c1_eps += 1
            else:
                c2_recs += n
                c2_eps += 1
        c1_rate = c1_recs / c1_eps if c1_eps else 0.0
        c2_rate = c2_recs / c2_eps if c2_eps else 0.0
        ratio = c2_rate / c1_rate if c1_rate else None
        source_stats[src] = {
            "c1_records": c1_recs, "c1_episodes": c1_eps, "c1_rate": c1_rate,
            "c2_records": c2_recs, "c2_episodes": c2_eps, "c2_rate": c2_rate,
            "c2_c1_ratio": ratio,
        }
        print(f"  {src}: C1={c1_rate:.2f}/ep ({c1_recs}/{c1_eps}), "
              f"C2={c2_rate:.2f}/ep ({c2_recs}/{c2_eps}), "
              f"ratio={ratio:.2f}" if ratio else
              f"  {src}: C1={c1_rate:.2f}/ep ({c1_recs}/{c1_eps}), "
              f"C2={c2_rate:.2f}/ep ({c2_recs}/{c2_eps}), ratio=N/A")

    # Identify largest-delta source
    deltas = {
        src: (s["c2_rate"] - s["c1_rate"])
        for src, s in source_stats.items()
        if s["c2_c1_ratio"] is not None
    }
    largest_delta_src = max(deltas, key=lambda s: deltas[s])
    print(f"\nLargest absolute delta source: {largest_delta_src} "
          f"(+{deltas[largest_delta_src]:.2f} records/ep)")

    # Category-level breakdown for largest-delta source
    cat_stats: dict[str, dict[str, dict]] = {}
    src = largest_delta_src
    cat_c1: dict[str, dict[str, int]] = defaultdict(lambda: {"recs": 0, "eps": set()})
    cat_c2: dict[str, dict[str, int]] = defaultdict(lambda: {"recs": 0, "eps": set()})
    for ep in all_eps:
        camp = ep_campaigns[ep]
        for r in by_ep_src[ep].get(src, []):
            cat = r["category"] or "TM_UNKNOWN"
            if camp == "C1":
                cat_c1[cat]["recs"] += 1
                cat_c1[cat]["eps"].add(ep)
            else:
                cat_c2[cat]["recs"] += 1
                cat_c2[cat]["eps"].add(ep)

    all_cats = sorted(set(cat_c1.keys()) | set(cat_c2.keys()))
    print(f"\n{src} category breakdown (C1 vs C2 records/covered-ep):")
    cat_breakdown = []
    for cat in all_cats:
        c1r = cat_c1[cat]["recs"]
        c1e = len(cat_c1[cat]["eps"])
        c2r = cat_c2[cat]["recs"]
        c2e = len(cat_c2[cat]["eps"])
        c1_rate_cat = c1r / c1e if c1e else 0.0
        c2_rate_cat = c2r / c2e if c2e else 0.0
        ratio_cat = c2_rate_cat / c1_rate_cat if c1_rate_cat else None
        cat_breakdown.append({
            "category": cat,
            "c1_records": c1r, "c1_episodes": c1e, "c1_rate": c1_rate_cat,
            "c2_records": c2r, "c2_episodes": c2e, "c2_rate": c2_rate_cat,
            "c2_c1_ratio": ratio_cat,
        })
        ratio_str = f"{ratio_cat:.2f}" if ratio_cat is not None else "N/A"
        print(f"  {cat:<32} C1={c1_rate_cat:.2f}/ep  C2={c2_rate_cat:.2f}/ep  "
              f"ratio={ratio_str}")

    # Cross-check: CC 39% delta replication with extended 140 episodes
    cc_s = source_stats["CC"]
    cc_delta_pct = (
        (cc_s["c2_rate"] - cc_s["c1_rate"]) / cc_s["c1_rate"] * 100
        if cc_s["c1_rate"] else None
    )
    print(f"\nCC delta cross-check (original finding: 39%):")
    print(f"  C1={cc_s['c1_rate']:.2f}/ep  C2={cc_s['c2_rate']:.2f}/ep  "
          f"delta={cc_delta_pct:.1f}%" if cc_delta_pct else
          f"  C1={cc_s['c1_rate']:.2f}/ep  C2={cc_s['c2_rate']:.2f}/ep  delta=N/A")

    # --- CSV ---
    csv_path = os.path.join(RESULTS_DIR, "x6_campaign_density.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "source", "c1_records", "c1_episodes", "c1_rate",
            "c2_records", "c2_episodes", "c2_rate", "c2_c1_ratio",
        ])
        writer.writeheader()
        for src in SOURCES:
            s = source_stats[src]
            writer.writerow({
                "source": src,
                "c1_records": s["c1_records"],
                "c1_episodes": s["c1_episodes"],
                "c1_rate": round(s["c1_rate"], 3),
                "c2_records": s["c2_records"],
                "c2_episodes": s["c2_episodes"],
                "c2_rate": round(s["c2_rate"], 3),
                "c2_c1_ratio": round(s["c2_c1_ratio"], 3) if s["c2_c1_ratio"] else "",
            })
    print(f"\nCSV written: {csv_path}")

    # --- Markdown ---
    md_path = os.path.join(RESULTS_DIR, "x6_campaign_density.md")
    with open(md_path, "w") as f:
        f.write("# X6: Campaign Density Delta Across All Four Sources\n\n")
        f.write("**Question:** Which extractor's record counts drive the C2 density "
                "delta over C1?\n\n")
        f.write(f"**Scope:** {len(all_eps)} episodes (full corpus)\n\n")
        f.write(f"**Date:** {date.today()}\n\n")
        f.write("---\n\n")

        f.write("## Key Findings\n\n")
        f.write(f"- Largest absolute delta: **{largest_delta_src}** "
                f"(+{deltas[largest_delta_src]:.2f} records/ep)\n")
        for src in SOURCES:
            s = source_stats[src]
            ratio_str = f"{s['c2_c1_ratio']:.2f}×" if s["c2_c1_ratio"] else "N/A"
            f.write(f"- {src}: C1={s['c1_rate']:.2f}/ep → C2={s['c2_rate']:.2f}/ep "
                    f"(ratio {ratio_str})\n")
        if cc_delta_pct is not None:
            f.write(f"- CC delta cross-check: {cc_delta_pct:.1f}% "
                    f"(original finding: 39%; scope now {source_stats['CC']['c1_episodes']+source_stats['CC']['c2_episodes']} episodes)\n")
        f.write("\n---\n\n")

        f.write("## Per-Source C1 vs C2 Records/Episode\n\n")
        f.write("| Source | C1 records | C1 eps | C1 rec/ep | "
                "C2 records | C2 eps | C2 rec/ep | C2/C1 ratio |\n")
        f.write("|--------|------------|--------|-----------|"
                "------------|--------|-----------|-------------|\n")
        for src in SOURCES:
            s = source_stats[src]
            ratio_str = f"{s['c2_c1_ratio']:.2f}×" if s["c2_c1_ratio"] else "N/A"
            f.write(f"| {src} | {s['c1_records']} | {s['c1_episodes']} | "
                    f"{s['c1_rate']:.2f} | {s['c2_records']} | {s['c2_episodes']} | "
                    f"{s['c2_rate']:.2f} | {ratio_str} |\n")
        f.write("\n---\n\n")

        f.write(f"## {largest_delta_src} Category Breakdown (C1 vs C2)\n\n")
        f.write(f"| Category | C1 recs | C1 eps | C1/ep | "
                f"C2 recs | C2 eps | C2/ep | C2/C1 |\n")
        f.write("|----------|---------|--------|-------|"
                "---------|--------|-------|-------|\n")
        for row in sorted(cat_breakdown, key=lambda x: -(
            (x["c2_rate"] - x["c1_rate"])
        )):
            ratio_str = f"{row['c2_c1_ratio']:.2f}×" if row["c2_c1_ratio"] else "N/A"
            f.write(f"| {row['category']} | {row['c1_records']} | {row['c1_episodes']} | "
                    f"{row['c1_rate']:.2f} | {row['c2_records']} | {row['c2_episodes']} | "
                    f"{row['c2_rate']:.2f} | {ratio_str} |\n")
        f.write("\n---\n\n")

        f.write("## CC Delta Cross-Check\n\n")
        cc_s = source_stats["CC"]
        f.write(f"Original finding (Compression Cadence findings §5 Q5): 39% delta "
                f"(C1=2.61/ep, C2=3.63/ep, 123-episode pool).\n\n")
        f.write(f"Cross-check with merged 140-episode set:\n")
        f.write(f"- C1: {cc_s['c1_rate']:.2f}/ep ({cc_s['c1_records']} records, "
                f"{cc_s['c1_episodes']} episodes)\n")
        f.write(f"- C2: {cc_s['c2_rate']:.2f}/ep ({cc_s['c2_records']} records, "
                f"{cc_s['c2_episodes']} episodes)\n")
        if cc_delta_pct is not None:
            f.write(f"- Delta: {cc_delta_pct:.1f}%\n")
        f.write("\n---\n\n")

        f.write("## Corpus-Level Summary\n\n")
        f.write(f"| Metric | Value |\n|--------|-------|\n")
        f.write(f"| Total episodes | {len(all_eps)} |\n")
        for src in SOURCES:
            s = source_stats[src]
            ratio_str = f"{s['c2_c1_ratio']:.2f}×" if s["c2_c1_ratio"] else "N/A"
            f.write(f"| {src} C2/C1 ratio | {ratio_str} |\n")
        f.write(f"| Largest delta source | {largest_delta_src} "
                f"(+{deltas[largest_delta_src]:.2f} rec/ep) |\n")
    print(f"Markdown written: {md_path}")

    return {
        "scope_eps": len(all_eps),
        "source_stats": {
            src: {k: v for k, v in s.items()}
            for src, s in source_stats.items()
        },
        "largest_delta_src": largest_delta_src,
        "cc_delta_pct": cc_delta_pct,
    }


if __name__ == "__main__":
    run()
