#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare multiple ARC-Golf solution folders task-by-task.

Default folders compared (relative to repo root):
- submission
- submission_better
- decompressed_submission
- decompressed_submission_better

Output:
- Console tables + insights
- JSON report (default: eval_compare.json)

Usage examples (from repo root):
  python arc_utils/compare_solutions.py --pretty
  python arc_utils/compare_solutions.py --folders submission submission_better --start 1 --end 200
  python arc_utils/compare_solutions.py --out reports/eval_compare_1_400.json
  python arc_utils/compare_solutions.py --no-progress
"""
import os, sys, re, json, time, shutil, importlib.util, copy, traceback
from typing import Dict, Any, List, Tuple, Union, Optional
import numpy as np

# Make sibling imports work anywhere
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from loader import load_task, _task_id_str
from score  import get_file_bytes, score_for_length

DEFAULT_FOLDERS = [
    "submission",
    "submission_better",
    "decompressed_submission",
    "decompressed_submission_better",
]
DEFAULT_OUT = os.path.join(REPO_ROOT, "eval_compare.json")

# ---------- Progress bar ----------
class ProgressBar:
    def __init__(self, total: int, label: str = ""):
        self.total = max(1, int(total))
        self.start = time.time()
        self.done = 0
        cols = shutil.get_terminal_size(fallback=(100, 24)).columns
        # Keep bar tidy within terminal width; leave room for label
        fixed = 38 + len(label)
        self.bar_width = max(10, min(50, cols - fixed))
        self.label = label

    def update(self, step: int = 1):
        self.done = min(self.total, self.done + step)
        frac = self.done / self.total
        filled = int(frac * self.bar_width)
        bar = "█" * filled + "░" * (self.bar_width - filled)
        elapsed = max(1e-9, time.time() - self.start)
        rate = self.done / elapsed
        remain = self.total - self.done
        eta = int(remain / rate) if rate > 0 else 0
        print(f"\r{self.label}[{bar}] {self.done}/{self.total}  ETA:{eta:>3}s", end="", flush=True)

    def finish(self):
        print()

# ---------- Minimal verifier (independent of evaluator.py path assumptions) ----------
_UNSAFE_CHARS_RE = re.compile(r"[^0-9,\[\]\s\.]")

def _run_and_sanitize(program, grid_in):
    result = program(copy.deepcopy(grid_in))
    dumped = json.dumps(result).replace("true","1").replace("false","0")
    if _UNSAFE_CHARS_RE.search(dumped):
        raise ValueError(f"Invalid output from user code: {dumped[:200]}")
    parsed = json.loads(dumped)
    return np.array(parsed, dtype=object)

def _verify_split(program, pairs):
    right = wrong = 0
    first_wrong_detail = None
    err_tb = ""
    for ex in pairs:
        try:
            user_arr = _run_and_sanitize(program, ex["input"])
            want_arr = np.array(ex["output"], dtype=object)
            ok = (user_arr.shape == want_arr.shape and (user_arr == want_arr).all())
            if ok:
                right += 1
            else:
                wrong += 1
                if first_wrong_detail is None:
                    first_wrong_detail = {
                        "input": ex["input"],
                        "expected": ex["output"],
                        "actual": user_arr.tolist(),
                    }
        except Exception:
            wrong += 1
            if not err_tb:
                err_tb = traceback.format_exc()
            if first_wrong_detail is None:
                first_wrong_detail = {
                    "input": ex["input"],
                    "expected": ex["output"],
                    "actual": None,
                }
    return right, wrong, first_wrong_detail, err_tb

def _import_solver_from(src_dir: str, task_id: Union[int, str]):
    tid = _task_id_str(task_id)
    file_path = os.path.join(src_dir, f"task{tid}.py")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Missing solver file: {file_path}")

    mod_name = f"cmp_{os.path.basename(src_dir)}_{tid}"
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = sys.modules[mod_name] = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    if not hasattr(mod, "p"):
        raise AttributeError(f"{file_path} does not define function p(g).")
    prog = getattr(mod, "p")
    if not callable(prog):
        raise TypeError(f"p in {file_path} is not callable.")
    return prog, file_path

# ---------- Core evaluate ----------
def _present_tasks(src_dir: str) -> Dict[int, str]:
    """Return {task_id: file_path} present in src_dir."""
    out: Dict[int, str] = {}
    if not os.path.isdir(src_dir):
        return out
    pat = re.compile(r"^task(\d{3})\.py$")
    for fn in os.listdir(src_dir):
        m = pat.match(fn)
        if m:
            out[int(m.group(1))] = os.path.join(src_dir, fn)
    return out

def _eval_one(src_dir: str, task_id: int) -> Dict[str, Any]:
    """Evaluate one task in a folder; always returns a dict with exists flag."""
    tid3 = _task_id_str(task_id)
    meta: Dict[str, Any] = {
        "exists": False, "passed": False, "bytes": 0, "score": 0.001,
        "arc_agi": {"pass": 0, "fail": 0}, "arc_gen": {"pass": 0, "fail": 0},
        "error": "",
        "file": os.path.join(os.path.relpath(src_dir, REPO_ROOT), f"task{tid3}.py"),
    }
    if not os.path.exists(os.path.join(src_dir, f"task{tid3}.py")):
        return meta

    meta["exists"] = True

    # Load examples
    tjson = load_task(task_id)
    agi_pairs = (tjson.get("train", []) + tjson.get("test", [])) or []
    gen_pairs = tjson.get("arc-gen", []) or []

    try:
        program, file_path = _import_solver_from(src_dir, task_id)
        agi_r, agi_w, _, _ = _verify_split(program, agi_pairs)
        gen_r, gen_w, _, _ = _verify_split(program, gen_pairs)

        passed_all = (agi_w == 0 and gen_w == 0)
        nbytes = get_file_bytes(file_path)
        score = score_for_length(nbytes, passed_all)

        meta.update({
            "passed": bool(passed_all),
            "bytes": int(nbytes),
            "score": float(score),
            "arc_agi": {"pass": int(agi_r), "fail": int(agi_w)},
            "arc_gen": {"pass": int(gen_r), "fail": int(gen_w)},
        })
    except Exception as e:
        meta["error"] = f"{type(e).__name__}: {e}"
    return meta

def evaluate_folders(folders: List[str], start: int, end: int,
                     progress: bool=True) -> Dict[str, Any]:
    abs_folders = [os.path.join(REPO_ROOT, f) for f in folders]
    for p in abs_folders:
        if not os.path.isdir(p):
            print(f"Warning: folder not found: {p}", file=sys.stderr)
    total_work = (end - start + 1) * len(folders)
    pb = ProgressBar(total_work, label="Comparing ") if progress and sys.stdout.isatty() else None

    tasks: Dict[str, Dict[str, Any]] = {}
    per_folder_summary: Dict[str, Dict[str, Any]] = {
        f: {"present":0,"solved":0,"failed":0,"missing":0,
            "total_score":0.0,"total_bytes":0,"avg_score":0.0,"avg_bytes_present":0.0}
        for f in folders
    }

    for tid in range(start, end+1):
        tkey = f"task{_task_id_str(tid)}.py"
        tasks[tkey] = {}
        # evaluate across folders
        for folder, absf in zip(folders, abs_folders):
            meta = _eval_one(absf, tid)
            tasks[tkey][folder] = meta

            # update per-folder summary
            if meta["exists"]:
                per_folder_summary[folder]["present"] += 1
                per_folder_summary[folder]["total_bytes"] += meta.get("bytes",0)
            else:
                per_folder_summary[folder]["missing"] += 1

            if meta.get("passed", False):
                per_folder_summary[folder]["solved"] += 1
            else:
                if meta["exists"]:
                    per_folder_summary[folder]["failed"] += 1

            per_folder_summary[folder]["total_score"] += float(meta.get("score",0.001))
            if pb: pb.update()

        # add per-task cross-folder deltas
        scores = {f: tasks[tkey][f]["score"] for f in folders}
        best_score = max(scores.values()) if scores else 0.0
        best_folders = [f for f,sc in scores.items() if sc == best_score]
        tasks[tkey]["_comparison"] = {
            "best_score": best_score,
            "best_folders": best_folders,
            "score_debt_by_folder": {f: (best_score - sc) for f,sc in scores.items()},
        }

    if pb: pb.finish()

    # finalize per-folder averages
    for f, s in per_folder_summary.items():
        total = (end - start + 1)
        present = s["present"]
        s["avg_score"] = s["total_score"]/total if total else 0.0
        s["avg_bytes_present"] = (s["total_bytes"]/present) if present else 0.0
        s["pass_rate"] = (s["solved"]/total) if total else 0.0

    # global insights
    # 1) best overall by total_score
    best_overall = sorted(
        ((f, s["total_score"]) for f,s in per_folder_summary.items()),
        key=lambda x: x[1], reverse=True
    )
    # 2) per-task wins tally
    wins = {f:0 for f in folders}
    ties = 0
    for tkey, row in tasks.items():
        bests = row["_comparison"]["best_folders"]
        if len(bests) == 1: wins[bests[0]] += 1
        else: ties += 1
    # 3) score debt per folder (how much each lags taskwise from best)
    score_debt = {f:0.0 for f in folders}
    for tkey, row in tasks.items():
        for f, debt in row["_comparison"]["score_debt_by_folder"].items():
            score_debt[f] += debt
    # 4) biggest gaps
    gaps = []
    for tkey, row in tasks.items():
        scores = {f: row[f]["score"] for f in folders if f in row}
        if not scores: continue
        mx, mn = max(scores.values()), min(scores.values())
        gaps.append((tkey, mx - mn))
    gaps.sort(key=lambda x: x[1], reverse=True)
    largest_gaps = gaps[:20]

    insights = {
        "best_overall_by_total_score": best_overall,
        "wins_by_folder": wins,
        "ties_count": ties,
        "score_debt_by_folder": score_debt,
        "largest_score_gaps_top20": largest_gaps,
    }

    return {"folders": folders, "summary": per_folder_summary,
            "insights": insights, "tasks": tasks}

# ---------- Pretty tables (pure stdlib) ----------
def _fmt_float(x, nd=3): return f"{x:.{nd}f}"
def _pad(s, w): return s[:w] if len(s)>w else s + " "*(w-len(s))

def print_overall_table(report: Dict[str, Any]) -> None:
    folders = report["folders"]
    s = report["summary"]
    cols = [
        ("Folder", 28),
        ("Present", 8),
        ("Solved", 7),
        ("Failed", 7),
        ("Missing", 8),
        ("TotalScore", 12),
        ("AvgScore", 10),
        ("AvgBytes", 10),
        ("Pass%", 7),
    ]
    header = " | ".join(_pad(name, w) for name,w in cols)
    sep = "-"*len(header)
    print(sep)
    print(header)
    print(sep)
    for f in folders:
        row = s[f]
        vals = [
            _pad(f, 28),
            _pad(str(row["present"]), 8),
            _pad(str(row["solved"]), 7),
            _pad(str(row["failed"]), 7),
            _pad(str(row["missing"]), 8),
            _pad(_fmt_float(row["total_score"],3), 12),
            _pad(_fmt_float(row["avg_score"],3), 10),
            _pad(_fmt_float(row["avg_bytes_present"],1), 10),
            _pad(_fmt_float(100*row["pass_rate"],1), 7),
        ]
        print(" | ".join(vals))
    print(sep)

def print_insights(report: Dict[str, Any]) -> None:
    ins = report["insights"]
    print("\n== Insights ==")
    print("- Best overall (by total score):")
    for f,score in ins["best_overall_by_total_score"]:
        print(f"  {f:28s}  total_score={_fmt_float(score,3)}")
    print(f"- Wins by folder: {ins['wins_by_folder']}  | ties={ins['ties_count']}")
    print("- Score debt by folder (lower is better; total gap from per-task best):")
    for f,debt in sorted(ins["score_debt_by_folder"].items(), key=lambda x:x[1]):
        print(f"  {f:28s}  debt={_fmt_float(debt,3)}")
    print("- Largest per-task score gaps (top 20):")
    for tkey,gap in ins["largest_score_gaps_top20"]:
        print(f"  {tkey}: Δscore={_fmt_float(gap,3)}")

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--folders", nargs="+", default=DEFAULT_FOLDERS,
                    help="Solution folders to compare (relative to repo root).")
    ap.add_argument("--start", type=int, default=1, help="First task id (default: 1)")
    ap.add_argument("--end", type=int, default=400, help="Last task id (default: 400)")
    ap.add_argument("--out", type=str, default=DEFAULT_OUT, help="Output JSON path")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    ap.add_argument("--no-progress", action="store_true", help="Disable TTY progress bar")
    args = ap.parse_args()

    # Resolve absolute paths and keep readable names
    folders = args.folders
    # Compute
    report = evaluate_folders(folders, args.start, args.end,
                              progress=(not args.no_progress))

    # Console output
    print_overall_table(report)
    print_insights(report)

    # Write JSON
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        if args.pretty:
            json.dump(report, f, indent=2)
        else:
            json.dump(report, f, separators=(",",":"))
    print(f"\nWrote report → {os.path.relpath(args.out, REPO_ROOT)}")

if __name__ == "__main__":
    main()