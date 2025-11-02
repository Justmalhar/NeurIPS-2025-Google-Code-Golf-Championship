import json, os
from typing import Dict, List, Any, Union

# Fallback demo task for task 0 (kept minimal)
_TASK_ZERO = {
    "train": [{"input": [[0]], "output": [[0]]}],
    "test": [],
    "arc-gen": [],
}

def _task_id_str(task_id: Union[int, str]) -> str:
    tid = int(task_id)
    return f"{tid:03d}"

def _candidate_paths(task_id: Union[int, str]) -> list:
    tid = _task_id_str(task_id)
    # local repo path
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
    local_path = os.path.join(here, "data", "tasks", f"task{tid}.json")
    # kaggle path
    kaggle_dir = "/kaggle/input/google-code-golf-2025"
    kaggle_path = os.path.join(kaggle_dir, f"task{tid}.json")
    return [local_path, kaggle_path]

def load_task(task_id: Union[int, str]) -> Dict[str, List[Dict[str, Any]]]:
    tid = int(task_id)
    if tid == 0:
        return _TASK_ZERO
    for path in _candidate_paths(task_id):
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    raise FileNotFoundError(f"task{_task_id_str(task_id)}.json not found in data/tasks or Kaggle input dir")