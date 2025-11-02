import os, importlib.util, sys, copy, json, re, traceback
import numpy as np
from typing import List, Tuple, Union
from loader import load_task, _task_id_str
from score import get_file_bytes, score_for_length
from viz import show_examples

# submission dir at repo root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
SUBMISSION_DIR = os.path.join(REPO_ROOT, "submission")

_UNSAFE_CHARS_RE = re.compile(r"[^0-9,\[\]\s\.]")

def _clone_grid(g):
    return [row[:] for row in g]

def _import_solver(task_id: Union[int, str]):
    tid = _task_id_str(task_id)
    file_path = os.path.join(SUBMISSION_DIR, f"task{tid}.py")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Missing solver file: {file_path}")

    mod_name = f"task{tid}"
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

def _grids_equal(a: List[List[int]], b: List[List[int]]) -> bool:
    if len(a) != len(b): return False
    for ra, rb in zip(a,b):
        if len(ra) != len(rb): return False
        for xa, xb in zip(ra,rb):
            if xa != xb: return False
    return True

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

def evaluate_task(task_id: Union[int, str], visual_debug: bool=False) -> Tuple[bool,float,int]:
    task_json = load_task(task_id)
    program, file_path = _import_solver(task_id)

    arc_agi_pairs = task_json.get("train", []) + task_json.get("test", [])
    arc_gen_pairs = task_json.get("arc-gen", [])

    agi_r, agi_w, agi_detail, agi_tb = _verify_split(program, arc_agi_pairs)
    gen_r, gen_w, gen_detail, gen_tb = _verify_split(program, arc_gen_pairs)

    passed_all = (agi_w == 0 and gen_w == 0)
    file_len = get_file_bytes(file_path)
    task_score = score_for_length(file_len, passed_all)

    if visual_debug:
        print(f"\nARC-AGI: {agi_r} pass / {agi_w} fail")
        print(f"ARC-GEN: {gen_r} pass / {gen_w} fail")
        if agi_tb or gen_tb:
            print("\nTraceback from first error:\n")
            print(agi_tb or gen_tb)
        bad = agi_detail or gen_detail
        if bad:
            print("\nFirst failing case (green=expected, red=actual):")
            expected_case = {"input": bad["input"], "output": bad["expected"]}
            actual_case   = {"input": bad["input"], "output": bad["actual"] if bad["actual"] is not None else []}
            print("Expected:")
            show_examples([expected_case], bgcolor=(200,255,200))
            print("Actual:")
            show_examples([actual_case], bgcolor=(255,200,200))

    return passed_all, task_score, file_len