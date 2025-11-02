#!/usr/bin/env python3
import os, sys, re, zlib, ast, json, time, shutil

# --- Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)
SRC_DIR    = os.path.join(REPO_ROOT, "submission")
DST_DIR    = os.path.join(REPO_ROOT, "decompressed")
MANIFEST   = os.path.join(DST_DIR, "manifest.json")

# --- Progress bar (same style as eval_all) ---
class ProgressBar:
    def __init__(self, total: int):
        self.total = max(1, int(total))
        self.start = time.time()
        self.done = self.decomp = self.copied = self.errors = 0
        cols = shutil.get_terminal_size(fallback=(100, 24)).columns
        self.bar_width = max(10, min(50, cols - 64))  # leave room for counters

    def update(self, done: int, decomp: int, copied: int, errors: int):
        self.done, self.decomp, self.copied, self.errors = done, decomp, copied, errors
        frac = self.done / self.total
        filled = int(frac * self.bar_width)
        bar = "█" * filled + "░" * (self.bar_width - filled)
        elapsed = max(1e-9, time.time() - self.start)
        rate = self.done / elapsed
        remain = self.total - self.done
        eta = int(remain / rate) if rate > 0 else 0
        # ✓D = decompressed, C = copied, E = errors
        print(f"\r[{bar}] {self.done}/{self.total}  ✓D{self.decomp} C{self.copied} E{self.errors}  ETA:{eta:>3}s",
              end="", flush=True)

    def finish(self):
        print()

# --- Compression patterns we support (no exec, pure parse) ---
# 1) zlib.decompress(bytes('…', 'L1'/'latin-1'/'latin1'))
PAT_BYTES_L1 = re.compile(
    r"zlib\.decompress\(\s*bytes\(\s*(?P<s>['\"].*?['\"])"
    r"\s*,\s*(?P<enc>['\"](?:L1|latin-1|latin1)['\"])"
    r"\s*\)\s*\)", re.DOTALL
)
# 2) zlib.decompress(b'…')   (capture the entire bytes literal as group 1)
PAT_BYTES_RAW = re.compile(
    r"zlib\.decompress\(\s*(?P<lit>b['\"].*?['\"])s*\)", re.DOTALL
)

def _maybe_decompress_text(src_text: str):
    """
    Try to extract compressed payload from source text (read as latin-1).
    Return (code_text, method) where method in {'bytes-L1','bytes-raw',None}.
    If not recognized/decompressed, return (None, None).
    """
    m = PAT_BYTES_L1.search(src_text)
    if m:
        try:
            # Safe-eval the inner string literal, then encode via latin-1 mapping.
            s = ast.literal_eval(m.group("s"))   # -> py str
            comp = s.encode("latin-1")
            out = zlib.decompress(comp)
            return out.decode("utf-8", "replace"), "bytes-L1"
        except Exception:
            return None, None

    m = PAT_BYTES_RAW.search(src_text)
    if m:
        try:
            lit = m.group("lit")                 # the full bytes literal e.g. b'...'
            comp = ast.literal_eval(lit)         # -> py bytes
            out = zlib.decompress(comp)
            return out.decode("utf-8", "replace"), "bytes-raw"
        except Exception:
            return None, None

    return None, None

def _process_file(src_path: str, dst_path: str):
    # Read as latin-1 so '#coding:L1' payloads roundtrip
    with open(src_path, "r", encoding="latin-1") as f:
        txt = f.read()

    code, method = _maybe_decompress_text(txt)
    if code is not None:
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(code)
        return {"action": "decompressed", "method": method,
                "in_bytes": len(txt.encode("latin-1")), "out_bytes": len(code.encode("utf-8"))}

    # Not recognized as compressed → copy as-is
    shutil.copyfile(src_path, dst_path)
    return {"action": "copied", "method": None,
            "in_bytes": os.path.getsize(src_path), "out_bytes": os.path.getsize(dst_path)}

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC_DIR, help="Source dir (default: submission)")
    ap.add_argument("--dst", default=DST_DIR, help="Destination dir (default: decompressed)")
    ap.add_argument("--no-progress", action="store_true", help="Disable TTY progress bar")
    args = ap.parse_args()

    src_dir, dst_dir = os.path.abspath(args.src), os.path.abspath(args.dst)
    if not os.path.isdir(src_dir):
        print(f"Source dir not found: {src_dir}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(dst_dir, exist_ok=True)

    pat = re.compile(r"^task(\d{3})\.py$")
    files = sorted([fn for fn in os.listdir(src_dir) if pat.match(fn)])
    total = len(files)
    use_progress = (not args.no_progress) and sys.stdout.isatty()
    pb = ProgressBar(total) if use_progress else None

    manifest = {"source": src_dir, "dest": dst_dir, "files": [], "summary": {}}
    n_done = n_decomp = n_copy = n_err = 0

    for fn in files:
        src = os.path.join(src_dir, fn)
        dst = os.path.join(dst_dir, fn)
        try:
            info = _process_file(src, dst)
            if info["action"] == "decompressed": n_decomp += 1
            elif info["action"] == "copied":     n_copy   += 1
            manifest["files"].append({"file": fn, **info})
        except Exception as e:
            n_err += 1
            manifest["files"].append({"file": fn, "action": "error", "error": f"{type(e).__name__}: {e}"})
        n_done += 1
        if pb: pb.update(n_done, n_decomp, n_copy, n_err)

    if pb: pb.finish()

    manifest["summary"] = {
        "total": total,
        "decompressed": n_decomp,
        "copied": n_copy,
        "errors": n_err,
    }
    with open(os.path.join(dst_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Processed {total} files → decompressed={n_decomp} copied={n_copy} errors={n_err}")
    print(f"Output: {dst_dir}")
    print(f"Manifest: {os.path.join(dst_dir, 'manifest.json')}")

if __name__ == "__main__":
    main()