#!/usr/bin/env python3
import os, sys, re, json, time, shutil, importlib.util, copy, traceback
from typing import Dict, Any, List, Tuple, Union, Callable, Optional
import numpy as np

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)  # for sibling imports

from loader import load_task, _task_id_str
from score  import get_file_bytes, score_for_length

DEFAULT_SRC = os.path.join(REPO_ROOT, "decompressed_submission")
DEFAULT_OUT = os.path.join(REPO_ROOT, "eval_results_decompressed.json")

# ---------- Progress bar ----------
class ProgressBar:
    def __init__(self, total: int):
        self.total = max(1, int(total))
        self.start = time.time()
        self.done = self.solved = self.failed = self.missing = 0
        cols = shutil.get_terminal_size(fallback=(100, 24)).columns
        self.bar_width = max(10, min(50, cols - 60))

    def update(self, done: int, solved: int, failed: int, missing: int):
        self.done, self.solved, self.failed, self.missing = done, solved, failed, missing
        frac = self.done / self.total
        filled = int(frac * self.bar_width)
        bar = "█" * filled + "░" * (self.bar_width - filled)
        elapsed = max(1e-9, time.time() - self.start)
        rate = self.done / elapsed
        remain = self.total - self.done
        eta = int(remain / rate) if rate > 0 else 0
        print(f"\r[{bar}] {self.done}/{self.total}  ✓{self.solved} ✗{self.failed} ∅{self.missing}  ETA:{eta:>3}s",
              end="", flush=True)

    def finish(self):
        print()

# ---------- Verification helpers (standalone; no dependency on evaluator.py) ----------
_UNSAFE_CHARS_RE = re.compile(r"[^0-9,\[\]\s\.]")

def _clone_grid(g):
    return [row[:] for row in g]

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
            if (user_arr.shape == want_arr.shape and (user_arr == want_arr).all()):
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

    mod_name = f"task{tid}_decompressed"
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

# ---------- Core logic ----------
def _task_paths_present(src_dir: str) -> Dict[int, str]:
    """Return {task_id: file_path} for task files present in src_dir."""
    out: Dict[int, str] = {}
    if not os.path.isdir(src_dir):
        return out
    pat = re.compile(r"^task(\d{3})\.py$")
    for fn in os.listdir(src_dir):
        m = pat.match(fn)
        if m:
            out[int(m.group(1))] = os.path.join(src_dir, fn)
    return out

def _eval_one(src_dir: str, task_id: int, file_exists: bool) -> Dict[str, Any]:
    """Evaluate a single task from src_dir; return a metadata dict."""
    tid3 = _task_id_str(task_id)
    meta: Dict[str, Any] = {
        "task_id": task_id,
        "file": os.path.join(os.path.relpath(src_dir, REPO_ROOT), f"task{tid3}.py"),
        "exists": file_exists,
        "bytes": 0,
        "score": 0.001,   # Kaggle minimal score when incorrect/missing
        "passed": False,
        "arc_agi": {"pass": 0, "fail": 0},
        "arc_gen": {"pass": 0, "fail": 0},
        "error": "",
    }

    # Load pairs to get counts even if file is missing
    tjson = load_task(task_id)
    agi_pairs = (tjson.get("train", []) + tjson.get("test", [])) or []
    gen_pairs = tjson.get("arc-gen", []) or []
    meta["arc_agi"]["fail"] = len(agi_pairs)  # will be corrected if we run
    meta["arc_gen"]["fail"] = len(gen_pairs)

    if not file_exists:
        return meta

    try:
        program, file_path = _import_solver_from(src_dir, task_id)
        agi_r, agi_w, _, agi_tb = _verify_split(program, agi_pairs)
        gen_r, gen_w, _, gen_tb = _verify_split(program, gen_pairs)

        passed_all = (agi_w == 0 and gen_w == 0)
        nbytes = get_file_bytes(file_path)
        score = score_for_length(nbytes, passed_all)

        meta.update({
            "bytes": nbytes,
            "score": score,
            "passed": bool(passed_all),
            "arc_agi": {"pass": int(agi_r), "fail": int(agi_w)},
            "arc_gen": {"pass": int(gen_r), "fail": int(gen_w)},
            "error": (agi_tb or gen_tb or ""),
        })
        return meta
    except Exception as e:
        meta["error"] = f"{type(e).__name__}: {e}"
        return meta

def evaluate_all(src_dir: str, start: int = 1, end: int = 400,
                 on_progress: Optional[Callable[[int, int, int, int, int], None]] = None) -> Dict[str, Any]:
    """
    Evaluate tasks in [start, end] from src_dir.
    on_progress(done, total, solved, failed, missing) is called after each task.
    """
    present = _task_paths_present(src_dir)
    results: List[Dict[str, Any]] = []

    total = end - start + 1
    total_score = 0.0
    total_bytes = 0
    n_present = n_solved = n_failed = n_missing = 0

    for idx, tid in enumerate(range(start, end + 1), 1):
        file_exists = tid in present
        meta = _eval_one(src_dir, tid, file_exists)
        results.append(meta)

        if file_exists:
            n_present += 1
            total_bytes += meta.get("bytes", 0)
        if meta.get("passed", False):
            n_solved += 1
        else:
            if file_exists:
                n_failed += 1
            else:
                n_missing += 1

        total_score += float(meta.get("score", 0.001))
        if on_progress:
            on_progress(idx, total, n_solved, n_failed, n_missing)

    # Collect failed and missing
    failed_tasks: List[Dict[str, Any]] = []
    missing_tasks: List[int] = []
    for m in results:
        if not m["exists"]:
            missing_tasks.append(m["task_id"])
        elif not m["passed"]:
            failed_tasks.append({
                "task_id": m["task_id"],
                "file": m["file"],
                "bytes": m["bytes"],
                "score": m["score"],
                "arc_agi": m["arc_agi"],
                "arc_gen": m["arc_gen"],
                "error": (m["error"][:400] if m["error"] else "")
            })

    summary = {
        "src_dir": os.path.relpath(src_dir, REPO_ROOT),
        "total_tasks": total,
        "present": n_present,
        "solved": n_solved,
        "failed": n_failed,
        "missing": n_missing,
        "total_score": total_score,
        "avg_score": (total_score / total),
        "total_bytes_present": total_bytes,
        "avg_bytes_present": (total_bytes / n_present) if n_present else 0.0,
    }

    return {
        "summary": summary,
        "failed_tasks": failed_tasks,
        "missing_tasks": missing_tasks,
        "tasks": results
    }

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=str, default=DEFAULT_SRC, help="Solver directory (default: decompressed/)")
    ap.add_argument("--start", type=int, default=1, help="First task id (default: 1)")
    ap.add_argument("--end", type=int, default=400, help="Last task id (default: 400)")
    ap.add_argument("--out", type=str, default=DEFAULT_OUT, help="Output JSON path")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON with indent")
    ap.add_argument("--no-progress", action="store_true", help="Disable TTY progress bar")
    args = ap.parse_args()

    src_dir = os.path.abspath(args.src)
    if not os.path.isdir(src_dir):
        print(f"Source solver dir not found: {src_dir}", file=sys.stderr)
        sys.exit(1)

    use_progress = (not args.no_progress) and sys.stdout.isatty()
    pb = ProgressBar(args.end - args.start + 1) if use_progress else None

    def _cb(done, total, solved, failed, missing):
        if pb:
            pb.update(done, solved, failed, missing)

    report = evaluate_all(src_dir, args.start, args.end, on_progress=_cb)
    if pb:
        pb.finish()

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        if args.pretty:
            json.dump(report, f, indent=2)
        else:
            json.dump(report, f, separators=(",", ":"))

    # small console summary
    s = report["summary"]
    print(f"Evaluated tasks {args.start}..{args.end} from {s['src_dir']}")
    print(f"present={s['present']} solved={s['solved']} failed={s['failed']} missing={s['missing']}")
    print(f"total_score={s['total_score']:.3f} avg_score={s['avg_score']:.3f}")
    print(f"avg_bytes_present={s['avg_bytes_present']:.1f}")

if __name__ == "__main__":
    main()