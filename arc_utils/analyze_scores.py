#!/usr/bin/env python3
import os, sys, json, math, argparse
from typing import List, Dict, Any, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_IN  = os.path.join(REPO_ROOT, "eval_results.json")
DEFAULT_OUT = os.path.join(REPO_ROOT, "eval_analysis.json")

def _load(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)

def _edges_from_step(step: int) -> List[float]:
    step = max(1, int(step))
    # Scores are [0.001 .. 2500]; build [0, step, 2*step, ..., 2500]
    n = math.ceil(2500/step)
    edges = [0.0] + [float(step*i) for i in range(1, n)] + [2500.0]
    # ensure unique & sorted
    out = sorted(set(edges))
    if out[0] > 0: out = [0.0] + out
    if out[-1] < 2500: out.append(2500.0)
    return out

def _edges_from_csv(csv: str) -> List[float]:
    e = sorted(set(float(x.strip()) for x in csv.split(",") if x.strip()!=""))
    if not e: return [0.0, 2500.0]
    if e[0] > 0: e = [0.0] + e
    if e[-1] < 2500: e.append(2500.0)
    return e

def _mk_bins(edges: List[float]) -> List[Tuple[float,float]]:
    # bins: [e[i], e[i+1]) except last which is inclusive on the right
    return [(edges[i], edges[i+1]) for i in range(len(edges)-1)]

def _label(lo: float, hi: float, last: bool) -> str:
    lo_i = int(lo+0.5)
    hi_i = int(hi+0.5)
    # use inclusive label for readability
    return f"{lo_i}–{hi_i}{'' if last else ''}"

def _assign_bin(score: float, bins: List[Tuple[float,float]]) -> int:
    # Place s into first bin with lo <= s < hi, except last where lo <= s <= hi
    s = float(score)
    for i, (lo, hi) in enumerate(bins):
        if i == len(bins)-1:
            if lo <= s <= hi: return i
        else:
            if lo <= s < hi: return i
    return len(bins)-1  # fallback

def analyze(results: Dict[str, Any], edges: List[float]) -> Dict[str, Any]:
    bins = _mk_bins(edges)
    labels = [_label(b[0], b[1], i==len(bins)-1) for i,b in enumerate(bins)]
    bucket: List[Dict[str, Any]] = [
        {"label": labels[i], "lo": bins[i][0], "hi": bins[i][1],
         "count": 0, "passed": 0, "failed": 0, "task_ids": []}
        for i in range(len(bins))
    ]

    tasks: List[Dict[str, Any]] = results.get("tasks", [])
    solved = failed = missing = present = 0
    for t in tasks:
        tid   = int(t["task_id"])
        sc    = float(t.get("score", 0.001))
        ex    = bool(t.get("exists", False))
        ok    = bool(t.get("passed", False))
        if ex: present += 1
        if ok: solved  += 1
        else:
            if ex: failed += 1
            else:  missing += 1
        bi = _assign_bin(sc, bins)
        b = bucket[bi]
        b["count"] += 1
        b["passed"] += int(ok)
        b["failed"] += int(not ok)
        b["task_ids"].append(tid)

    # Sort task lists inside each bin for readability
    for b in bucket:
        b["task_ids"].sort()

    # Helpful ranked views
    # Longest passing files by bytes
    passing = [t for t in tasks if t.get("passed")]
    longest_pass = sorted(passing, key=lambda x: x.get("bytes", 0), reverse=True)[:20]
    shortest_pass = sorted(passing, key=lambda x: x.get("bytes", 10**9))[:20]
    lowest_scores = sorted(tasks, key=lambda x: x.get("score", 0.001))[:20]
    highest_scores = sorted(tasks, key=lambda x: x.get("score", 0.001), reverse=True)[:20]

    return {
        "config": {
            "edges": edges,
            "bin_labels": labels,
            "source": "eval_results.json",
        },
        "summary": results.get("summary", {}),
        "bins": bucket,
        "failed_tasks": results.get("failed_tasks", []),
        "missing_tasks": results.get("missing_tasks", []),
        "top": {
            "longest_pass_by_bytes": [
                {"task_id": t["task_id"], "bytes": t.get("bytes", 0), "score": t.get("score", 0)}
                for t in longest_pass
            ],
            "shortest_pass_by_bytes": [
                {"task_id": t["task_id"], "bytes": t.get("bytes", 0), "score": t.get("score", 0)}
                for t in shortest_pass
            ],
            "lowest_scores": [
                {"task_id": t["task_id"], "bytes": t.get("bytes", 0), "score": t.get("score", 0), "exists": t.get("exists", False)}
                for t in lowest_scores
            ],
            "highest_scores": [
                {"task_id": t["task_id"], "bytes": t.get("bytes", 0), "score": t.get("score", 0)}
                for t in highest_scores
            ],
        },
    }

def print_table(analysis: Dict[str, Any]) -> None:
    bins = analysis["bins"]
    # Simple console table
    print("\nScore distribution:")
    print(f"{'bin':>12}  {'count':>5}  {'passed':>6}  {'failed':>6}")
    for b in bins:
        print(f"{b['label']:>12}  {b['count']:5d}  {b['passed']:6d}  {b['failed']:6d}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=DEFAULT_IN, help="Path to eval_results.json")
    ap.add_argument("--out", dest="out", default=DEFAULT_OUT.replace(".json","_analysis.json"),
                    help="Path to write analysis JSON")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--step", type=int, default=250, help="Uniform bin step (default 250)")
    g.add_argument("--edges", type=str, help="Comma-separated score edges, e.g. '0,1000,1500,2000,2300,2400,2450,2500'")
    args = ap.parse_args()

    if not os.path.exists(args.inp):
        print(f"Input not found: {args.inp}", file=sys.stderr); sys.exit(1)

    edges = _edges_from_csv(args.edges) if args.edges else _edges_from_step(args.step)
    data = _load(args.inp)
    analysis = analyze(data, edges)

    with open(args.out, "w") as f:
        json.dump(analysis, f, indent=2)

    print_table(analysis)
    s = analysis.get("summary", {})
    print("\nSummary:",
          f"present={s.get('present',0)}",
          f"solved={s.get('solved',0)}",
          f"failed={s.get('failed',0)}",
          f"missing={s.get('missing',0)}",
          f"total_score={s.get('total_score',0):.3f}",
          f"avg_score={s.get('avg_score',0):.3f}")

if __name__ == "__main__":
    main()