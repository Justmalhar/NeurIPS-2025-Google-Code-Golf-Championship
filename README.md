# NeurIPS 2025 - Google Code Golf Championship (ARC-AGI)

This repo helps build and validate 400 minimal Python solvers for ARC tasks.

## Layout

- `data/tasks/`
  - Contains `taskNNN.json` for N=001..400.
  - Each file has:
    - `train`: list of {input, output}
    - `test`: list of {input, output}
    - `arc-gen`: list of {input, output}
- `submission/`
  - Contains `taskNNN.py` for N=001..400.
  - Each file defines a solver for that task.

## Dev utilities

- `arc_utils/loader.py`
  - Load a task spec into memory.
- `arc_utils/viz.py`
  - Pretty-print grids (2D list[int]) as color blocks or digits.
- `arc_utils/evaluator.py`
  - Run a task's solver against all examples from train/test/arc-gen.
- `arc_utils/score.py`
  - Compute byte length of a solver file and score contribution.

## Setup

1.	Create and activate a virtual environment. From the project root (where .venv/ should live):
    ```bash
    # Create venv
    python3 -m venv .venv
    ```
2.  Then activate it:
    
    macOS / Linux (bash, zsh):
    ```bash
    source .venv/bin/activate
    ```

    Windows (PowerShell):
    ```bash
    .\.venv\Scripts\Activate.ps1
    ```

    Windows (cmd.exe):
    ```bash
    .\.venv\Scripts\activate.bat
    ```

    Once activated, your terminal prompt should display:
    ```bash
    (.venv)
    ```

3.  Install Dependencies:
    ```bash
    pip3 install -r requirments.txt
    ```

4.  Run the setup scripts. Generate the scaffold for all 400 submission files:
    ```bash
    python3 arc_utils/gen_scaffold.py
    ```

5.  Test the environment:
    ```bash
    python3 arc_utils/eval_task.py --task 1 --show --debug
    ```

## Workflow

1. `python gen_scaffold.py`
   - Generates empty `submission/taskNNN.py` with stub function `p(g)`.

2. Edit e.g. `submission/task137.py` until it solves the task.

3. Visualize a task:
   ```bash
   python eval_task.py --task 137 --show
    ```

4.	Evaluate correctness + score for that task:
    ```bash
    python eval_task.py --task 137
    ```

5.	When you’re ready to Kaggle submit:
	•	Zip ONLY the submission/ dir contents into submission.zip.
	•	Each file must be standalone, stdlib-only.

---

