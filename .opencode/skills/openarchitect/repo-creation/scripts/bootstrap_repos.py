from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_common_python_on_path() -> None:
    common_python = Path(__file__).resolve().parents[2] / "common" / "python"
    common_python_str = str(common_python)
    if common_python_str not in sys.path:
        sys.path.insert(0, common_python_str)


_ensure_common_python_on_path()

from openarchitect_skill_common.repo_bootstrap import bootstrap_repos


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap downstream repos from solution-index.yml + solution-build-plan.yml.")
    parser.add_argument("--solution-index", type=Path, default=Path("solution-index.yml"))
    parser.add_argument("--build-plan", type=Path, default=Path("architecture/solution/solution-build-plan.yml"))
    parser.add_argument("--workdir", type=Path, default=Path(".work/repos"))
    parser.add_argument("--solution-repo-root", type=Path, default=Path("."))
    parser.add_argument("--no-clone", action="store_true", help="Do not git clone; operate on existing local directories under --workdir.")
    parser.add_argument("--dry-run", action="store_true", help="Create directories only; do not write files.")
    parser.add_argument("--snapshot-id", help="Override snapshot id under inputs/ (default commit-<sha> or snapshot-unknown).")
    parser.add_argument("--upstream-repo-url", help="Override upstream repo_url for inputs/source.yml.")
    parser.add_argument("--upstream-commit", help="Override upstream commit for inputs/source.yml.")
    args = parser.parse_args()

    return bootstrap_repos(
        solution_repo_root=args.solution_repo_root,
        solution_index_path=args.solution_index,
        build_plan_path=args.build_plan,
        workdir=args.workdir,
        no_clone=args.no_clone,
        dry_run=args.dry_run,
        snapshot_id=args.snapshot_id,
        upstream_repo_url=args.upstream_repo_url,
        upstream_commit=args.upstream_commit,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
