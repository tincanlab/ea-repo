#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from openarchitect.infra.config import load_postgres_config
from openarchitect.storage.store import WorkspaceStore


def _repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _local_state_path(repo_root: Path) -> Path:
    return repo_root / ".openarchitect" / "local.yml"


def _read_simple_yaml(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _artifact_specs(
    repo_root: Path, entries: Iterable[str], *, allow_missing: bool
) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"invalid artifact '{entry}'; expected kind=git_path")
        kind, git_path = entry.split("=", 1)
        normalized_kind = kind.strip()
        normalized_git_path = git_path.strip().replace("\\", "/")
        if not normalized_kind or not normalized_git_path:
            raise ValueError(f"invalid artifact '{entry}'; empty kind/path")
        file_path = (repo_root / normalized_git_path).resolve()
        if not file_path.exists() or not file_path.is_file():
            if allow_missing:
                continue
            raise ValueError(f"artifact file not found: {normalized_git_path}")
        parsed.append((normalized_kind, normalized_git_path))
    return parsed


def _resolve_workspace_id(repo_root: Path, explicit_workspace_id: str) -> str:
    normalized = explicit_workspace_id.strip()
    if normalized:
        return normalized
    state = _read_simple_yaml(_local_state_path(repo_root))
    workspace_id = str(state.get("workspace_id", "")).strip()
    if workspace_id:
        return workspace_id
    raise ValueError(
        "workspace_id is required (pass --workspace-id or set .openarchitect/local.yml)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="register_workspace_artifacts.py",
        description=(
            "Bulk-register repo artifacts into an OpenArchitect workspace using "
            "kind + git_path + text."
        ),
    )
    parser.add_argument(
        "--workspace-id",
        default="",
        help="Target workspace_id. If omitted, reads .openarchitect/local.yml.",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Artifact mapping in form kind=git_path. Can be repeated.",
    )
    parser.add_argument(
        "--default-artifact",
        action="append",
        default=[],
        help=(
            "Default mapping in form kind=git_path. Used only when --artifact is not set. "
            "Can be repeated."
        ),
    )
    parser.add_argument(
        "--created-by",
        default="skill_migration",
        help="created_by value for registered artifacts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print actions without writing artifacts.",
    )
    args = parser.parse_args()

    repo_root = _repo_root(Path.cwd())
    workspace_id = _resolve_workspace_id(repo_root, args.workspace_id)

    if args.artifact:
        artifacts = _artifact_specs(repo_root, args.artifact, allow_missing=False)
    else:
        artifacts = _artifact_specs(
            repo_root, args.default_artifact, allow_missing=True
        )
    if not artifacts:
        print("[INFO] No artifacts selected (no defaults found and no --artifact provided).")
        return 0

    print(f"[INFO] repo_root={repo_root}")
    print(f"[INFO] workspace_id={workspace_id}")
    print(f"[INFO] dry_run={args.dry_run}")
    for kind, git_path in artifacts:
        print(f"[INFO] artifact kind={kind} git_path={git_path}")

    if args.dry_run:
        return 0

    store = WorkspaceStore(cfg=load_postgres_config())
    for kind, git_path in artifacts:
        file_path = (repo_root / git_path).resolve()
        text = file_path.read_text(encoding="utf-8")
        artifact = store.write_artifact(
            workspace_id=workspace_id,
            kind=kind,
            content={"text": text, "git_path": git_path},
            created_by=args.created_by,
            inputs={"git_path": git_path, "source": "register_workspace_artifacts.py"},
        )
        print(
            "[OK] "
            f"kind={kind} git_path={git_path} artifact_id={artifact.artifact_id} "
            f"version={artifact.version}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
