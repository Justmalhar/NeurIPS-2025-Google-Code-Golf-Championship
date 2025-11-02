import os

def get_file_bytes(path: str) -> int:
    with open(path, "rb") as f:
        return len(f.read())

def score_for_length(file_len_bytes: int, passed: bool) -> float:
    if not passed:
        return 0.001
    base = 2500 - file_len_bytes
    return float(base if base > 1 else 1)