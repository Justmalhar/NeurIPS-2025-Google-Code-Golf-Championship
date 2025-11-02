#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create a minimal CSV from eval_compare.json with ONLY:
submission_bytes, submission_better_bytes, decompressed_submission_bytes,
decompressed_submission_better_bytes, is_submission_better

- Assumes eval_compare.json is produced by compare_solutions.py
- Uses score to decide is_submission_better (strictly higher than 'submission')
- Rows are sorted by taskNNN, but task id is NOT included in CSV (per request)
"""

import os, sys, json, csv, re
from typing import Any, Dict, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)
DEFAULT_IN = os.path.join(REPO_ROOT, "eval_compare.json")
DEFAULT_OUT= os.path.join(REPO_ROOT, "eval_compare_min.csv")
TASK_RE = re.compile(r"task(\d{3})\.py$")

FOLDERS = [
    "submission",
    "submission_better",
    "decompressed_submission",
    "decompressed_submission_better",
]

def _load_by_task(report: Dict[str, Any]) -> Dict[str, Any]:
    # Support either {"by_task": {...}} or {"tasks": {...}}
    return report.get("by_task") or report.get("tasks") or {}

def _tasknum(k: str) -> int:
    m = TASK_RE.match(k)
    return int(m.group(1)) if m else 0

def _bytes_for(row: Dict[str, Any], folder: str):
    meta = row.get(folder, {})
    # Only emit bytes if file exists; else empty cell
    if meta.get("exists", False):
        return int(meta.get("bytes", 0))
    return ""

def _score_for(row: Dict[str, Any], folder: str) -> float:
    meta = row.get(folder, {})
    try:
        return float(meta.get("score", 0.001))
    except Exception:
        return 0.001

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="inp",  default=DEFAULT_IN,  help="Path to eval_compare.json")
    ap.add_argument("--out", dest="outp", default=DEFAULT_OUT, help="Path to output CSV")
    args = ap.parse_args()

    if not os.path.exists(args.inp):
        print(f"Input not found: {args.inp}", file=sys.stderr)
        sys.exit(2)

    with open(args.inp, "r") as f:
        report = json.load(f)

    by_task = _load_by_task(report)
    if not by_task:
        print("No tasks found in JSON (expected keys: 'by_task' or 'tasks').", file=sys.stderr)
        sys.exit(2)

    # Build rows (no Task column by request)
    header = [
        "submission_bytes",
        "submission_better_bytes",
        "decompressed_submission_bytes",
        "decompressed_submission_better_bytes",
        "is_submission_better",
    ]

    items = sorted(by_task.items(), key=lambda kv: _tasknum(kv[0]))
    rows: List[List[Any]] = []
    for task_key, row in items:
        sub_b   = _bytes_for(row, "submission")
        sub2_b  = _bytes_for(row, "submission_better")
        dsub_b  = _bytes_for(row, "decompressed_submission")
        dsub2_b = _bytes_for(row, "decompressed_submission_better")

        # "better" decided by score strictly greater
        s_sub  = _score_for(row, "submission")
        s_sub2 = _score_for(row, "submission_better")
        is_better = "true" if s_sub2 > s_sub else "false"

        rows.append([sub_b, sub2_b, dsub_b, dsub2_b, is_better])

    os.makedirs(os.path.dirname(os.path.abspath(args.outp)), exist_ok=True)
    with open(args.outp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.outp}")

if __name__ == "__main__":
    main()