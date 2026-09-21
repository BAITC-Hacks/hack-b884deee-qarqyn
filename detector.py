#!/usr/bin/env python3
"""
paint_defect_detector.py

Simulates the inspection-station model in a conveyor paint-line:

    part painted -> camera takes a picture -> this model measures the
    percentage of the square's surface covered in red paint -> the
    result is what the plant-floor screen would display:

        coverage >= threshold (default 50%)  ->  green screen, "APPROVED"
        coverage <  threshold                ->  red screen,   "DEFECT: remove part"

Usage
-----
    # Single image
    python3 paint_defect_detector.py path/to/part.png

    # A whole folder of pictures (e.g. one photo per part coming off the line)
    python3 paint_defect_detector.py path/to/folder/ --threshold 50

    # Custom threshold (percent) and a stricter definition of "red"
    python3 paint_defect_detector.py path/to/folder/ --threshold 60

Exit code is 0 if every part APPROVED, 1 if at least one part was flagged
DEFECT (handy if you want to wire this into a CI-style pass/fail check).
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def red_coverage_percent(image_path: Path, red_dominance: int = 40, min_red: int = 90) -> float:
    """
    Returns the percentage (0-100) of pixels in the image classified as
    "paint red".

    A pixel counts as red paint if:
      - its Red channel is at least `min_red` (not counting near-black noise)
      - its Red channel exceeds both Green and Blue by at least `red_dominance`
        (so it's clearly red, not gray/white/orange/brown, etc.)

    These two knobs can be tuned to match the real paint color and the
    camera/lighting setup on the actual line.
    """
    img = Image.open(image_path).convert("RGB")
    arr = np.asarray(img, dtype=np.int16)  # H x W x 3

    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

    is_red = (r >= min_red) & ((r - g) >= red_dominance) & ((r - b) >= red_dominance)

    total_pixels = arr.shape[0] * arr.shape[1]
    red_pixels = int(is_red.sum())

    return red_pixels / total_pixels * 100.0


def inspect(image_path: Path, threshold: float) -> dict:
    coverage = red_coverage_percent(image_path)
    approved = coverage >= threshold
    verdict = "APPROVED" if approved else "DEFECT: remove part"
    return {
        "file": image_path.name,
        "coverage_pct": round(coverage, 2),
        "threshold_pct": threshold,
        "approved": approved,
        "verdict": verdict,
    }


def print_screen(result: dict) -> None:
    """Prints a plain-text stand-in for the plant-floor status screen."""
    color = "GREEN" if result["approved"] else "RED"
    bar = "=" * 46
    print(bar)
    print(f" SCREEN: [{color}]")
    print(f" PART:   {result['file']}")
    print(f" RED COVERAGE: {result['coverage_pct']}%  (threshold: {result['threshold_pct']}%)")
    print(f" MESSAGE: {result['verdict']}")
    print(bar)
    print()


def collect_images(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    raise FileNotFoundError(f"No such file or directory: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Paint-coverage defect detector for square parts.")
    parser.add_argument("path", type=Path, help="Image file or folder of images to inspect")
    parser.add_argument("--threshold", type=float, default=50.0, help="Minimum accepted red coverage percent (default: 50)")
    parser.add_argument("--quiet", action="store_true", help="Only print the summary table, not the per-part screen output")
    args = parser.parse_args()

    try:
        images = collect_images(args.path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if not images:
        print(f"No images found in {args.path}", file=sys.stderr)
        return 2

    results = []
    for img_path in images:
        result = inspect(img_path, args.threshold)
        results.append(result)
        if not args.quiet:
            print_screen(result)

    # Summary table
    print("SUMMARY")
    print(f"{'file':35s} {'coverage%':>10s} {'verdict':>22s}")
    for r in results:
        print(f"{r['file']:35s} {r['coverage_pct']:>10.2f} {r['verdict']:>22s}")

    n_defect = sum(1 for r in results if not r["approved"])
    n_total = len(results)
    print()
    print(f"{n_total - n_defect}/{n_total} APPROVED, {n_defect}/{n_total} DEFECT")

    return 1 if n_defect > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
