#!/usr/bin/env python3
"""Render the Xiapin SVG through FFmpeg's SVG decoder."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("size", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.size < 1 or args.size > 4096:
        parser.error("size must be between 1 and 4096")

    root = Path(__file__).resolve().parents[1]
    icon = root / "icons" / "xiapin.svg"
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        parser.error("FFmpeg with SVG support is required")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(icon),
        "-frames:v", "1", "-vf",
        f"scale={args.size}:{args.size}:flags=lanczos", "-y",
        str(args.output.resolve()),
    ], check=True)


if __name__ == "__main__":
    main()
