#!/usr/bin/env python3
"""Copy bundled tmf_commons into a target project.

Usage:
  python copy_tmf_commons.py --dest C:/path/to/project
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", required=True, help="Destination project root")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parents[1]
    src = skill_dir / "assets" / "tmf_commons"
    dest_root = Path(args.dest).resolve()
    dest = dest_root / "tmf_commons"

    if not src.exists():
        raise SystemExit(f"tmf_commons not found at {src}")

    if dest.exists():
        shutil.rmtree(dest)

    shutil.copytree(src, dest)
    print(f"Copied {src} -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
