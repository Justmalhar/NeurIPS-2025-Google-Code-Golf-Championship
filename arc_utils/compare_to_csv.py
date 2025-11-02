#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert eval_compare.json (from compare_solutions.py) to a CSV.

- One row per task (taskNNN.py)
- Columns per submission folder with scores (and optional bytes/pass)
- BestScore, BestFolder (ties joined by ';'), Gap (best - worst among chosen folders)

The script is resilient to either JSON shape:
  { "by_task": { ... } }   <-- preferred (compare_solutions.py)
  { "tasks":   { ... } }   <-- older print script expectation
"""

import os, sys, json, csv, re
from typing import Any, Dict, List, Tuple, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)
DEFAULT_IN = os.path.join(REPO_ROOT, "eval_compare.json")
DEFAULT_OUT= os.path.join(REPO_ROOT, "eval_compare.csv")
TASK_RE = re.compile(r"task(\d{3})\.py$")

def num_from_taskkey(k: str) -> int:
    m = TASK_RE.match(k)
    return int(m.group(1)) if m else 0

def ensure_folders(report: Dict[str, Any], by_task: Dict[str, Any], pick: Optional[List[str]]) -> List[str]:
    if pick:
        return pick
    # Prefer explicit list from report
    if isinstance(report.get("folders"), list) and report["folders"]:
        return list(report["folders"])
    # Derive from first task row
    for _, row in by_task.items():
        return [k for k in row.keys() if isinstance(row[k], dict)]
    return []

def fmt_score(x: float) -> float:
    return float(x)

def load_tasks(report: Dict[str, Any]) -> Dict[str, Any]:
    return report.get("by_task") or report.get("tasks") or {}

def best_and_gap(row: Dict[str, Any], folders: List[str]) -> Tuple[float, List[str], float]:
    scores = []
    per_folder: Dict[float, List[str]] = {}
    for f in folders:
        if f in row and isinstance(row[f], dict):
            s = float(row[f].get("score", 0.001))
            scores.append(s)
            per_folder.setdefault(s, []).append(f)
    if not scores:
        return 0.0, [], 0.0
    best = max(scores)
    worst = min(scores)
    return best, per_folder.get(best, []), best - worst

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="inp",  default=DEFAULT_IN,  help="Path to eval_compare.json")
    ap.add_argument("--out", dest="outp", default=DEFAULT_OUT, help="Path to output CSV")
    ap.add_argument("--folders", nargs="+", help="Subset/order of folders to include (default: from JSON)")
    ap.add_argument("--only-diff", action="store_true", help="Only include tasks where folder scores differ")
    ap.add_argument("--include-bytes", action="store_true", help="Add <folder>_bytes columns")
    ap.add_argument("--include-pass",  action="store_true", help="Add <folder>_pass columns (1/0)")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of rows (0=all)")
    ap.add_argument("--offset", type=int, default=0, help="Skip first N rows")
    args = ap.parse_args()

    if not os.path.exists(args.inp):
        print(f"Input not found: {args.inp}", file=sys.stderr)
        sys.exit(2)

    with open(args.inp, "r") as f:
        report = json.load(f)

    by_task = load_tasks(report)
    if not by_task:
        print("No tasks found in JSON (expected keys: 'by_task' or 'tasks').", file=sys.stderr)
        sys.exit(2)

    folders = ensure_folders(report, by_task, args.folders)
    if not folders:
        print("Could not determine folders to include. Use --folders.", file=sys.stderr)
        sys.exit(2)

    # Prepare column headers
    cols: List[str] = ["Task"]
    for f in folders:
        cols.append(f"{f}_score")
        if args.include_pass:  cols.append(f"{f}_pass")
        if args.include_bytes: cols.append(f"{f}_bytes")
    cols += ["BestScore", "BestFolder", "Gap"]

    # Collect and sort rows
    items = sorted(by_task.items(), key=lambda kv: num_from_taskkey(kv[0]))

    rows_out: List[List[Any]] = []
    for task_key, row in items:
        # if only-diff, check if scores differ
        scores_for_diff = [row[f]["score"] for f in folders if f in row]
        if args.only_diff and len(set(scores_for_diff)) <= 1:
            continue

        best, best_folders, gap = best_and_gap(row, folders)
        r: List[Any] = [task_key]
        for f in folders:
            meta = row.get(f, {})
            score = fmt_score(meta.get("score", 0.001))
            r.append(score)
            if args.include_pass:
                r.append(1 if meta.get("passed", False) else 0)
            if args.include_bytes:
                r.append(int(meta.get("bytes", 0)) if meta.get("exists", False) else None)
        r.append(fmt_score(best))
        r.append(";".join(best_folders))
        r.append(fmt_score(gap))
        rows_out.append(r)

    # offset/limit
    if args.offset: rows_out = rows_out[args.offset:]
    if args.limit:  rows_out = rows_out[:args.limit]

    # Write CSV
    os.makedirs(os.path.dirname(os.path.abspath(args.outp)), exist_ok=True)
    with open(args.outp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows_out)

    print(f"Wrote {len(rows_out)} rows to {args.outp}")
    print(f"Folders: {', '.join(folders)}")
    if args.only_diff:
        print("Note: only tasks with differing scores included.")

if __name__ == "__main__":
    main()