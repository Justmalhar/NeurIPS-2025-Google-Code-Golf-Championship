#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Print a terminal table from eval_compare.json with per-task, per-folder scores.

Default input: eval_compare.json at repo root (created by compare_solutions.py)

Features:
- Shows every task row with score per folder
- Highlights best score(s) per task (color)
- Optional: show only rows where folders differ
- Sort by task id or by gap between best and worst
- Limit/offset for pagination
- Optional: include pass/fail markers per folder
- Optional: include bytes per folder
"""

import os, sys, json, re, shutil, math
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)
DEFAULT_IN = os.path.join(REPO_ROOT, "eval_compare.json")

# ---------- color helpers ----------
def supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("TERM", "") not in ("dumb", "")

class C:
    _ok = supports_color()
    @staticmethod
    def g(s): return f"\033[1;32m{s}\033[0m" if C._ok else s  # green bold
    @staticmethod
    def y(s): return f"\033[33m{s}\033[0m" if C._ok else s   # yellow
    @staticmethod
    def r(s): return f"\033[31m{s}\033[0m" if C._ok else s   # red
    @staticmethod
    def d(s): return f"\033[90m{s}\033[0m" if C._ok else s   # dim gray
    @staticmethod
    def b(s): return f"\033[1m{s}\033[0m" if C._ok else s    # bold
    @staticmethod
    def off(): C._ok = False

# ---------- misc ----------
TASK_RE = re.compile(r"task(\d{3})\.py$")

def num_from_taskkey(k: str) -> int:
    m = TASK_RE.match(k)
    return int(m.group(1)) if m else 0

def fmt_score(x: float) -> str:
    # Print as int if it's integral; else 3 decimal places
    return str(int(x)) if abs(x - round(x)) < 1e-9 else f"{x:.3f}"

def pad(s: str, w: int) -> str:
    return s if len(s) >= w else s + " " * (w - len(s))

def cut(s: str, w: int) -> str:
    return s if len(s) <= w else s[:max(0, w-1)] + "…"

def compute_col_widths(tasks: List[Tuple[str, Dict[str, Any]]],
                       folders: List[str],
                       include_pass: bool,
                       include_bytes: bool,
                       max_width: int) -> Dict[str, int]:
    # Base widths
    w = {}
    w["Task"] = max(10, len("Task"))
    for tk, row in tasks:
        w["Task"] = max(w["Task"], len(tk))

    # Each folder column = score (and optional status, bytes)
    for f in folders:
        lab = f
        w[f] = max(8, len(lab))
        # scan scores for width needs
        for _, r in tasks:
            if f not in r: continue
            sc = r[f].get("score", 0.001)
            s = fmt_score(sc)
            if include_pass:
                s += " " + ("✓" if r[f].get("passed") else "✗")
            if include_bytes and r[f].get("exists"):
                s += f" ({r[f].get('bytes',0)})"
            w[f] = max(w[f], len(s))

    w["Best"] = max(6, len("Best"))
    w["Gap"]  = max(5, len("Gap"))
    # Measure data for best & gap
    for _, r in tasks:
        scores = [r[f]["score"] for f in folders if f in r]
        if scores:
            w["Best"] = max(w["Best"], len(fmt_score(max(scores))))
            gap = fmt_score(max(scores)-min(scores))
            w["Gap"]  = max(w["Gap"], len(gap))

    # Try to fit within terminal: shrink folder names if needed
    fixed = w["Task"] + w["Best"] + w["Gap"] + 3*3  # 3 separators between these blocks
    per_sep = 3
    total = fixed + sum(w[f] for f in folders) + per_sep*len(folders)
    cols = shutil.get_terminal_size(fallback=(160, 24)).columns
    target = min(max_width or cols, cols)
    if total > target:
        # try shrinking folder label text (prefix kept)
        for f in folders:
            # reduce to at least 8
            w[f] = max(8, w[f] - 2)
            total = fixed + sum(w[ff] for ff in folders) + per_sep*len(folders)
            if total <= target: break
    return w

def row_cells(task_key: str,
              row: Dict[str, Any],
              folders: List[str],
              include_pass: bool,
              include_bytes: bool,
              colorize: bool) -> Dict[str, str]:
    # Determine per-row best score
    scores = {f: row[f]["score"] for f in folders if f in row}
    best = max(scores.values()) if scores else 0.0
    gap  = best - (min(scores.values()) if scores else 0.0)
    cells = {}
    cells["Task"] = task_key
    cells["Best"] = fmt_score(best)
    cells["Gap"]  = fmt_score(gap)

    for f in folders:
        if f not in row:
            cells[f] = "—"
            continue
        meta = row[f]
        s = fmt_score(meta.get("score", 0.001))
        if include_pass:
            s += " " + ("✓" if meta.get("passed") else "✗")
        if include_bytes and meta.get("exists"):
            s += f" ({meta.get('bytes',0)})"
        if colorize and f in scores and scores[f] == best:
            s = C.g(s)
        elif colorize and meta.get("exists") and not meta.get("passed"):
            s = C.r(s)  # failing present file
        elif colorize and not meta.get("exists"):
            s = C.d("—")
        cells[f] = s
    return cells

def print_table(report: Dict[str, Any],
                folders: List[str],
                only_diff: bool,
                sort_key: str,
                limit: int,
                offset: int,
                include_pass: bool,
                include_bytes: bool,
                no_color: bool,
                max_width: int) -> None:
    if no_color:
        C.off()

    # Collect rows
    all_items = sorted(report["tasks"].items(), key=lambda kv: num_from_taskkey(kv[0]))
    rows: List[Tuple[str, Dict[str, Any]]] = []
    for tk, row in all_items:
        # require selected folders present in the JSON row keys (they always are; may be missing file)
        # filter: only_diff -> at least one score different
        scs = [row[f]["score"] for f in folders if f in row]
        if only_diff and (len(set(scs)) <= 1):
            continue
        rows.append((tk, row))
    # Sort
    if sort_key in ("gap_desc", "gap_asc"):
        def gap_of(r):
            scores = [r[f]["score"] for f in folders if f in r]
            return (max(scores)-min(scores)) if scores else -1
        rows.sort(key=lambda kv: gap_of(kv[1]), reverse=(sort_key=="gap_desc"))
    elif sort_key == "task":
        rows.sort(key=lambda kv: num_from_taskkey(kv[0]))
    # slice
    if offset: rows = rows[offset:]
    if limit:  rows = rows[:limit]

    # Widths
    widths = compute_col_widths(rows, folders, include_pass, include_bytes, max_width)

    # Header
    head_cols = [("Task", widths["Task"])]
    for f in folders:
        head_cols.append((f, widths[f]))
    head_cols += [("Best", widths["Best"]), ("Gap", widths["Gap"])]
    header = " | ".join(pad(c, w) for c, w in head_cols)
    sep = "-" * len(header)
    print(sep)
    print(C.b(header))
    print(sep)

    # Body
    for tk, row in rows:
        cells = row_cells(tk, row, folders, include_pass, include_bytes, colorize=True)
        parts = [pad(cut(cells["Task"], widths["Task"]), widths["Task"])]
        for f in folders:
            parts.append(pad(cut(cells[f], widths[f]), widths[f]))
        parts.append(pad(cells["Best"], widths["Best"]))
        parts.append(pad(cells["Gap"],  widths["Gap"]))
        print(" | ".join(parts))
    print(sep)
    print(f"Rows: {len(rows)}  |  Folders: {', '.join(folders)}")

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=DEFAULT_IN, help="Path to eval_compare.json")
    ap.add_argument("--folders", nargs="+", help="Subset/order of folders to display (default: from JSON)")
    ap.add_argument("--only-diff", action="store_true", help="Show only tasks where scores differ across folders")
    ap.add_argument("--sort", choices=["task","gap_desc","gap_asc"], default="task", help="Sort order")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of rows (0 = all)")
    ap.add_argument("--offset", type=int, default=0, help="Skip first N rows")
    ap.add_argument("--include-pass", action="store_true", help="Append ✓/✗ after each score")
    ap.add_argument("--include-bytes", action="store_true", help="Append (bytes) after each present file")
    ap.add_argument("--no-color", action="store_true", help="Disable colors")
    ap.add_argument("--max-width", type=int, default=0, help="Max table width (0=auto)")
    args = ap.parse_args()

    if args.no_color: C.off()

    if not os.path.exists(args.inp):
        print(f"Input not found: {args.inp}", file=sys.stderr)
        sys.exit(2)

    with open(args.inp, "r") as f:
        report = json.load(f)

    folders = args.folders or report.get("folders") or []
    if not folders:
        print("No folders found in JSON and none provided via --folders", file=sys.stderr)
        sys.exit(2)

    print_table(report, folders, args.only_diff, args.sort, args.limit, args.offset,
                args.include_pass, args.include_bytes, args.no_color, args.max_width)

if __name__ == "__main__":
    main()