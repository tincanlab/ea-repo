#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    skill_dir = Path(__file__).resolve().parents[1]
    shared_script = (
        skill_dir.parent / "common" / "scripts" / "register_workspace_artifacts.py"
    )
    cmd = [
        sys.executable,
        str(shared_script),
        "--default-artifact",
        "use_cases_markdown=architecture/requirements/use-cases.md",
        "--default-artifact",
        "use_cases_structured=architecture/requirements/use-cases.yml",
        *sys.argv[1:],
    ]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
