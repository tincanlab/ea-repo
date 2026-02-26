#!/usr/bin/env python3
"""Register domain-architecture repo artifacts into workspace.

Thin wrapper around the shared register_workspace_artifacts.py.
Requires --domain argument to locate the correct domain folder.

Usage:
    python register_workspace_artifacts.py --domain billing --dry-run
    python register_workspace_artifacts.py --domain billing
    python register_workspace_artifacts.py --domain billing --workspace-id <id>
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(prog="register_workspace_artifacts.py")
    parser.add_argument("--domain", required=True, help="Domain name (folder under architecture/domains/)")
    parser.add_argument("remaining", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    domain = args.domain
    skill_dir = Path(__file__).resolve().parents[1]
    shared_script = (
        skill_dir.parent / "common" / "scripts" / "register_workspace_artifacts.py"
    )

    base = f"architecture/domains/{domain}"
    cmd = [
        sys.executable,
        str(shared_script),
        "--default-artifact",
        f"domain_design={base}/domain-design.yml",
        "--default-artifact",
        f"component_specs={base}/component-specs.yml",
        "--default-artifact",
        f"domain_data_model={base}/data-model.yml",
        "--default-artifact",
        f"domain_workflows={base}/workflows.yml",
        *args.remaining,
    ]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
