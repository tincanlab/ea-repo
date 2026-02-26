#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def _repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _local_state_path() -> Path:
    return _repo_root(Path.cwd()) / ".openarchitect" / "local.yml"


def _read_state(path: Path) -> dict[str, str]:
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


def _write_state(path: Path, state: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}: {value}" for key, value in sorted(state.items()) if value]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(prog="persist_local_state.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    show = sub.add_parser("show")
    show.add_argument("--path-only", action="store_true")

    set_cmd = sub.add_parser("set")
    set_cmd.add_argument("--workspace-id", required=True)
    set_cmd.add_argument("--workspace-name", default="")
    set_cmd.add_argument("--tenant-id", default="")

    sub.add_parser("clear")

    args = parser.parse_args()
    path = _local_state_path()

    if args.cmd == "show":
        if args.path_only:
            print(path)
            return 0
        state = _read_state(path)
        print(f"path: {path}")
        print(f"exists: {path.exists()}")
        for key in ("workspace_id", "workspace_name", "tenant_id"):
            print(f"{key}: {state.get(key, '')}")
        return 0

    if args.cmd == "set":
        state = {
            "workspace_id": args.workspace_id.strip(),
            "workspace_name": args.workspace_name.strip(),
            "tenant_id": args.tenant_id.strip(),
        }
        _write_state(path, state)
        print(f"persisted: {path}")
        return 0

    if path.exists():
        path.unlink()
    print(f"cleared: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
