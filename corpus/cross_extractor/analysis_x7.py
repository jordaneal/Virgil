"""
analysis_x7.py — X7: Event clustering across all four sources.

Question: Do events from EC, TM, LR, CC cluster temporally within episodes,
or distribute independently?

Scope: 80 episodes (all-four intersection).
Cluster definition: ≥3 events from ≥2 different sources within a 15-turn window.
Independence baseline: permute source labels within each episode (100 shuffles),
compare observed multi-source cluster count to permutation mean.
"""

import csv
import os
import random
import sys
from collections import defaultdict
from datetime import date
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x_utils

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

CLUSTER_WINDOW = 15
MIN_EVENTS = 3
MIN_SOURCES = 2
N_PERMS = 100
PERM_SEED = 42
TOP_N = 10
SPOT_CHECK_N = 5
SPOT_CHECK_SEED = 42


def find_clusters(events: list[dict], window: int = CLUSTER_WINDOW,
                  min_events: int = MIN_EVENTS,
                  min_sources: int = MIN_SOURCES) -> list[dict]:
    """
    Greedy sliding-window cluster detection.
    Anchor on each event in turn order; if the window [T, T+window-1] contains
    ≥min_events events from ≥min_sources distinct sources, record the cluster
    and advance past the window end (no double-counting).

    Returns list of cluster dicts.
    """
    if not events:
        return []
    events_sorted = sorted(events, key=lambda e: (e["turn_number"], e["source"]))
    clusters = []
    skip_until = -1
    for i, anchor in enumerate(events_sorted):
        t_start = anchor["turn_number"]
        if t_start < skip_until:
            continue
        t_end = t_start + window - 1
        window_evs = [
            e for e in events_sorted[i:]
            if e["turn_number"] <= t_end
        ]
        sources_in = set(e["source"] for e in window_evs)
        if len(window_evs) >= min_events and len(sources_in) >= min_sources:
            clusters.append({
                "turn_start": t_start,
                "turn_end": t_end,
                "size": len(window_evs),
                "sources": sorted(sources_in),
                "n_sources": len(sources_in),
                "events": window_evs,
            })
            skip_until = t_end + 1
    return clusters


def permute_sources(events: list[dict], rng: random.Random) -> list[dict]:
    """Return events with source labels shuffled (turn numbers preserved)."""
    sources = [e["source"] for e in events]
    rng.shuffle(sources)
    return [{**e, "source": s} for e, s in zip(events, sources)]


def run():
    scope_eps = sorted(x_utils.get_all_four_intersection())
    print(f"X7 scope: {len(scope_eps)} episodes (all-four intersection)")

    # Load streams
    streams: dict[str, dict] = {}
    for ep in scope_eps:
        streams[ep] = x_utils.load_episode_stream(ep)

    # Per-episode events (all sources)
    ep_events: dict[str, list[dict]] = {}
    for ep in scope_eps:
        ep_events[ep] = [
            {
                "source": ev["source"],
                "turn_number": ev["turn_number"],
                "category": ev.get("category"),
                "episode_position_pct": ev.get("episode_position_pct"),
            }
            for ev in streams[ep]["events"]
        ]

    # --- Observed clusters ---
    ep_clusters: dict[str, list[dict]] = {}
    for ep in scope_eps:
        ep_clusters[ep] = find_clusters(ep_events[ep])

    total_obs = sum(len(cls) for cls in ep_clusters.values())
    cluster_counts = sorted(len(ep_clusters[ep]) for ep in scope_eps)
    mean_clusters = total_obs / len(scope_eps)
    median_clusters = cluster_counts[len(cluster_counts) // 2]
    max_clusters = max(cluster_counts)
    n_zero = sum(1 for c in cluster_counts if c == 0)

    print(f"\nObserved clusters: {total_obs} total across {len(scope_eps)} episodes")
    print(f"  Mean={mean_clusters:.2f}  Median={median_clusters}  "
          f"Max={max_clusters}  Zero-cluster episodes={n_zero}")

    # --- Source-pair participation matrix ---
    pair_counts: dict[tuple, int] = defaultdict(int)
    for ep, clusters in ep_clusters.items():
        for cl in clusters:
            srcs = cl["sources"]
            for a, b in combinations(srcs, 2):
                pair_counts[(a, b)] += 1

    all_srcs = ["EC", "TM", "LR", "CC"]
    print("\nSource-pair participation (clusters containing both sources):")
    for a, b in combinations(all_srcs, 2):
        key = tuple(sorted([a, b]))
        print(f"  {a}+{b}: {pair_counts[key]}")

    # n-source distribution
    n_src_dist: dict[int, int] = defaultdict(int)
    for ep, clusters in ep_clusters.items():
        for cl in clusters:
            n_src_dist[cl["n_sources"]] += 1
    print("\nCluster n-source distribution:")
    for ns in sorted(n_src_dist):
        print(f"  {ns} sources: {n_src_dist[ns]} clusters")

    # --- Top 10 strongest clusters (by size desc, then n_sources desc) ---
    all_clusters_flat = [
        {"episode": ep, **cl}
        for ep, clusters in ep_clusters.items()
        for cl in clusters
    ]
    top_clusters = sorted(
        all_clusters_flat,
        key=lambda c: (-c["size"], -c["n_sources"], c["turn_start"]),
    )[:TOP_N]
    print(f"\nTop {TOP_N} strongest clusters (by size):")
    for tc in top_clusters:
        print(f"  {tc['episode']} t={tc['turn_start']}-{tc['turn_end']} "
              f"size={tc['size']} sources={tc['sources']}")

    # --- Independence test via permutation ---
    print(f"\nPermutation independence test ({N_PERMS} shuffles, seed={PERM_SEED})...")
    rng = random.Random(PERM_SEED)
    perm_totals = []
    for _ in range(N_PERMS):
        perm_total = 0
        for ep in scope_eps:
            shuffled = permute_sources(ep_events[ep], rng)
            perm_total += len(find_clusters(shuffled))
        perm_totals.append(perm_total)
    perm_mean = sum(perm_totals) / len(perm_totals)
    perm_std = (sum((x - perm_mean) ** 2 for x in perm_totals) / len(perm_totals)) ** 0.5
    excess = total_obs - perm_mean
    z_score = excess / perm_std if perm_std > 0 else None
    print(f"  Observed: {total_obs}  Permuted mean: {perm_mean:.1f}  "
          f"Excess: {excess:.1f}  Z={z_score:.2f}" if z_score else
          f"  Observed: {total_obs}  Permuted mean: {perm_mean:.1f}  "
          f"Excess: {excess:.1f}")

    # --- Spot-check top 5 clusters ---
    print(f"\n--- Spot-check: top {SPOT_CHECK_N} clusters against stream files ---")
    spot_lines = []
    all_verified = True
    for tc in top_clusters[:SPOT_CHECK_N]:
        ep = tc["episode"]
        stream = streams[ep]
        # Verify each event in the cluster exists in the stream
        verified_count = 0
        for ce in tc["events"]:
            in_stream = any(
                ev["source"] == ce["source"]
                and ev["turn_number"] == ce["turn_number"]
                for ev in stream["events"]
            )
            if in_stream:
                verified_count += 1
        all_in = verified_count == len(tc["events"])
        if not all_in:
            all_verified = False
        src_cats = "+".join(
            f"{ce['source']}/{ce['category'] or 'UNK'}"
            for ce in sorted(tc["events"], key=lambda e: e["turn_number"])
        )
        line = (f"ep={ep} t={tc['turn_start']}-{tc['turn_end']} "
                f"size={tc['size']} sources={tc['sources']} "
                f"verified={verified_count}/{len(tc['events'])} "
                f"events=[{src_cats}]")
        print(f"  {line}")
        spot_lines.append(line)

    # --- Per-episode cluster count distribution ---
    dist: dict[int, int] = defaultdict(int)
    for ep in scope_eps:
        dist[len(ep_clusters[ep])] += 1

    # --- CSV: per-episode summary ---
    csv_path = os.path.join(RESULTS_DIR, "x7_event_clustering.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "episode", "n_clusters", "max_cluster_size", "max_cluster_sources",
            "has_4src_cluster",
        ])
        writer.writeheader()
        for ep in sorted(ep_clusters.keys()):
            cls = ep_clusters[ep]
            if cls:
                max_cl = max(cls, key=lambda c: (c["size"], c["n_sources"]))
                writer.writerow({
                    "episode": ep,
                    "n_clusters": len(cls),
                    "max_cluster_size": max_cl["size"],
                    "max_cluster_sources": max_cl["n_sources"],
                    "has_4src_cluster": any(c["n_sources"] == 4 for c in cls),
                })
            else:
                writer.writerow({
                    "episode": ep, "n_clusters": 0,
                    "max_cluster_size": 0, "max_cluster_sources": 0,
                    "has_4src_cluster": False,
                })
    print(f"\nCSV written: {csv_path}")

    # --- Markdown ---
    md_path = os.path.join(RESULTS_DIR, "x7_event_clustering.md")
    with open(md_path, "w") as f:
        f.write("# X7: Event Clustering Across All Four Sources\n\n")
        f.write("**Question:** Do events from EC, TM, LR, CC cluster temporally "
                "within episodes, or distribute independently?\n\n")
        f.write(f"**Scope:** {len(scope_eps)} episodes (all-four intersection)\n\n")
        f.write(f"**Cluster definition:** ≥{MIN_EVENTS} events from ≥{MIN_SOURCES} "
                f"different sources within a {CLUSTER_WINDOW}-turn window\n\n")
        f.write(f"**Independence test:** {N_PERMS} source-label permutations "
                f"(seed={PERM_SEED})\n\n")
        f.write(f"**Date:** {date.today()}\n\n")
        f.write("---\n\n")

        f.write("## Key Findings\n\n")
        f.write(f"- Total clusters observed: **{total_obs}**\n")
        f.write(f"- Mean clusters per episode: **{mean_clusters:.2f}** "
                f"(median {median_clusters}, max {max_clusters})\n")
        f.write(f"- Episodes with zero clusters: **{n_zero}**\n")
        f.write(f"- Permutation baseline: {perm_mean:.1f} "
                f"(±{perm_std:.1f})\n")
        f.write(f"- Excess vs. independence: **+{excess:.1f}** clusters "
                f"(Z={z_score:.2f})\n" if z_score else
                f"- Excess vs. independence: +{excess:.1f} clusters\n")
        f.write(f"- 4-source clusters: **{n_src_dist.get(4, 0)}**\n")
        f.write(f"- Most common co-clustering pair: ")
        if pair_counts:
            top_pair = max(pair_counts, key=lambda k: pair_counts[k])
            f.write(f"**{top_pair[0]}+{top_pair[1]}** ({pair_counts[top_pair]} clusters)\n")
        f.write("\n---\n\n")

        f.write("## Per-Episode Cluster Count Distribution\n\n")
        f.write("| Clusters/episode | Episodes |\n|------------------|----------|\n")
        for k in sorted(dist.keys()):
            f.write(f"| {k} | {dist[k]} |\n")
        f.write("\n---\n\n")

        f.write("## Source-Pair Participation Matrix\n\n")
        f.write("Count = clusters containing events from both listed sources.\n\n")
        # Build header
        src_list = all_srcs
        f.write("| | " + " | ".join(src_list) + " |\n")
        f.write("|---|" + "---|" * len(src_list) + "\n")
        for a in src_list:
            row = f"| **{a}** |"
            for b in src_list:
                if a == b:
                    row += " — |"
                else:
                    key = tuple(sorted([a, b]))
                    row += f" {pair_counts[key]} |"
            f.write(row + "\n")
        f.write("\n---\n\n")

        f.write(f"## Top {TOP_N} Strongest Clusters\n\n")
        f.write("| Rank | Episode | Turn window | Size | Sources | n-sources |\n")
        f.write("|------|---------|-------------|------|---------|----------|\n")
        for i, tc in enumerate(top_clusters, 1):
            f.write(f"| {i} | {tc['episode']} | "
                    f"{tc['turn_start']}–{tc['turn_end']} | "
                    f"{tc['size']} | {'+'.join(tc['sources'])} | "
                    f"{tc['n_sources']} |\n")
        f.write("\n---\n\n")

        f.write("## Independence Test\n\n")
        f.write(f"Method: shuffle source labels within each episode ({N_PERMS} permutations). "
                f"Preserves event timing; destroys multi-source co-occurrence signal. "
                f"Compares observed multi-source cluster count to permuted mean.\n\n")
        f.write(f"| Metric | Value |\n|--------|-------|\n")
        f.write(f"| Observed clusters | {total_obs} |\n")
        f.write(f"| Permutation mean | {perm_mean:.1f} |\n")
        f.write(f"| Permutation std | {perm_std:.1f} |\n")
        f.write(f"| Excess | {excess:.1f} |\n")
        if z_score is not None:
            f.write(f"| Z-score | {z_score:.2f} |\n")
        f.write("\n---\n\n")

        f.write("## Spot-Check Results\n\n")
        f.write(f"Top {SPOT_CHECK_N} clusters verified against stream files.\n\n")
        for line in spot_lines:
            f.write(f"    {line}\n")
        f.write(f"\n{'All' if all_verified else 'NOT all'} spot-checked cluster "
                "events confirmed in stream.\n\n")
        f.write("---\n\n")

        f.write("## N-Source Distribution\n\n")
        f.write("| Sources in cluster | Count |\n|--------------------|-------|\n")
        for ns in sorted(n_src_dist.keys()):
            f.write(f"| {ns} | {n_src_dist[ns]} |\n")
        f.write("\n---\n\n")

        f.write("## Corpus-Level Summary\n\n")
        f.write(f"| Metric | Value |\n|--------|-------|\n")
        f.write(f"| Episodes in scope | {len(scope_eps)} |\n")
        f.write(f"| Total clusters | {total_obs} |\n")
        f.write(f"| Mean clusters/ep | {mean_clusters:.2f} |\n")
        f.write(f"| Max clusters/ep | {max_clusters} |\n")
        f.write(f"| Zero-cluster episodes | {n_zero} |\n")
        f.write(f"| Permutation baseline | {perm_mean:.1f} (±{perm_std:.1f}) |\n")
        f.write(f"| Excess vs independence | +{excess:.1f} "
                f"(Z={z_score:.2f}) |\n" if z_score else
                f"| Excess vs independence | +{excess:.1f} |\n")
        f.write(f"| 4-source clusters | {n_src_dist.get(4, 0)} |\n")
    print(f"Markdown written: {md_path}")

    return {
        "scope_eps": len(scope_eps),
        "total_obs_clusters": total_obs,
        "mean_clusters": mean_clusters,
        "max_clusters": max_clusters,
        "n_zero_eps": n_zero,
        "perm_mean": perm_mean,
        "perm_std": perm_std,
        "excess": excess,
        "z_score": z_score,
        "n_src_dist": dict(n_src_dist),
        "pair_counts": {f"{a}+{b}": pair_counts[(a, b)]
                        for a, b in combinations(all_srcs, 2)},
    }


if __name__ == "__main__":
    run()
