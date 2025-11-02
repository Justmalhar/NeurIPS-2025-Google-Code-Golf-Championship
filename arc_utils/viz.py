from typing import List, Optional
import matplotlib.pyplot as plt
import numpy as np

# Kaggle palette
PALETTE_RGB = [
    (0, 0, 0),
    (30, 147, 255),
    (250, 61, 49),
    (78, 204, 48),
    (255, 221, 0),
    (153, 153, 153),
    (229, 59, 163),
    (255, 133, 28),
    (136, 216, 241),
    (147, 17, 49),
]

def show_examples(examples, bgcolor=(255,255,255)):
    """
    Render list of {input,output} pairs side-by-side using matplotlib.
    This is almost identical to Google's show_examples().
    """
    # overall canvas size
    width, height, offset = 0, 0, 1
    for ex in examples:
        grid, outp = ex["input"], ex["output"]
        width += len(grid[0]) + 1 + len(outp[0]) + 4
        height = max(height, max(len(grid), len(outp)) + 4)

    # fill background
    image = [[bgcolor for _ in range(width)] for _ in range(height)]

    # paint cell colors
    offset = 1
    for ex in examples:
        grid, outp = ex["input"], ex["output"]
        gw, ow = len(grid[0]), len(outp[0])
        for r,row in enumerate(grid):
            for c,cell in enumerate(row):
                image[r+2][offset+c+1] = PALETTE_RGB[cell]
        offset += gw + 1
        for r,row in enumerate(outp):
            for c,cell in enumerate(row):
                image[r+2][offset+c+1] = PALETTE_RGB[cell]
        offset += ow + 4

    fig = plt.figure(figsize=(10,5))
    ax = fig.add_axes([0,0,1,1])
    ax.imshow(np.array(image))

    # draw gridlines
    offset = 1
    for ex in examples:
        grid, outp = ex["input"], ex["output"]
        gw, gh = len(grid[0]), len(grid)
        ow, oh = len(outp[0]), len(outp)

        ax.hlines([r+1.5 for r in range(gh+1)],
                  xmin=offset+0.5, xmax=offset+gw+0.5, color="black")
        ax.vlines([offset+c+0.5 for c in range(gw+1)],
                  ymin=1.5, ymax=gh+1.5, color="black")
        offset += gw + 1

        ax.hlines([r+1.5 for r in range(oh+1)],
                  xmin=offset+0.5, xmax=offset+ow+0.5, color="black")
        ax.vlines([offset+c+0.5 for c in range(ow+1)],
                  ymin=1.5, ymax=oh+1.5, color="black")
        offset += ow + 2

        ax.vlines([offset+0.5], ymin=-0.5, ymax=height-0.5, color="black")
        offset += 2

    ax.set_xticks([])
    ax.set_yticks([])

def show_task_examples(task_json: dict, limit_per_split: Optional[int] = 1) -> None:
    """
    Text-mode fallback: just print numeric grids to stdout for sanity.
    (Good in terminal / SSH without display.)
    We keep this from our earlier version because it's fast to glance.
    """
    def _print_grid(grid: List[List[int]]):
        for row in grid:
            print(" ".join(str(v) for v in row))

    for split in ["train", "test", "arc-gen"]:
        pairs = task_json.get(split, [])
        if not pairs:
            continue
        print(f"\n=== {split.upper()} EXAMPLES ===")
        for i, pair in enumerate(pairs):
            if limit_per_split is not None and i >= limit_per_split:
                break
            print(f"\n[{split} {i}] INPUT:")
            _print_grid(pair["input"])
            print(f"[{split} {i}] OUTPUT:")
            _print_grid(pair["output"])