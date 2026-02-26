#!/usr/bin/env python3
"""Register enterprise-architecture repo artifacts into workspace.

Thin wrapper around the shared register_workspace_artifacts.py with
default artifact mappings for the enterprise-architecture skill.
"""
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
        "enterprise_architecture=architecture/enterprise/target-architecture.yml",
        "--default-artifact",
        "capability_map=architecture/enterprise/capability-map.yml",
        "--default-artifact",
        "portfolio_assessment=architecture/enterprise/portfolio-assessment.yml",
        "--default-artifact",
        "governance=architecture/enterprise/governance.yml",
        *sys.argv[1:],
    ]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
