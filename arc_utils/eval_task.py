#!/usr/bin/env python3
import argparse
from loader import load_task
from viz import show_task_examples
from evaluator import evaluate_task

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, help="Task id (e.g. 1 or 137 or 003)")
    ap.add_argument("--show", action="store_true", help="Show text-mode examples")
    ap.add_argument("--debug", action="store_true", help="Visual diff + traceback on fail")
    args = ap.parse_args()

    tjson = load_task(args.task)

    if args.show:
        show_task_examples(tjson, limit_per_split=1)

    passed, score_val, nbytes = evaluate_task(args.task, visual_debug=args.debug)

    print("\n=== RESULT ===")
    print(f"Task:           {args.task}")
    print(f"Passed all I/O: {passed}")
    print(f"File bytes:     {nbytes}")
    print(f"Task score:     {score_val}")

if __name__ == "__main__":
    main()