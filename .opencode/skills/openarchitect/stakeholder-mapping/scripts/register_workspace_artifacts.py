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
        "stakeholder_map=architecture/requirements/stakeholders.md",
        "--default-artifact",
        "stakeholder_map_structured=architecture/requirements/stakeholders.yml",
        *sys.argv[1:],
    ]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
