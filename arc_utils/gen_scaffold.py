#!/usr/bin/env python3
import os

RANGE_START = 1
RANGE_END   = 400  # inclusive

# repo root = parent directory of this script's directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

SUBMISSION_DIR = os.path.join(REPO_ROOT, "submission")
os.makedirs(SUBMISSION_DIR, exist_ok=True)

TEMPLATE = """def p(g):
    # TODO: implement task-specific transformation
    # g is a list of rows, each row is a list of ints 0-9
    # return a new grid (list of lists of ints)
    # For now we just return the input unchanged.
    return [r[:] for r in g]
"""

def main():
    for tid in range(RANGE_START, RANGE_END + 1):
        fname = f"task{tid:03d}.py"
        fpath = os.path.join(SUBMISSION_DIR, fname)
        if not os.path.exists(fpath):
            with open(fpath, "w") as f:
                f.write(TEMPLATE)
            print(f"Created {fpath}")
        else:
            print(f"Skipped {fpath} (already exists)")

if __name__ == "__main__":
    main()