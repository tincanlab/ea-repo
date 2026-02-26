#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _extract_domain_hint(domain_md_text: str) -> str:
    if not domain_md_text:
        return ""

    patterns = [
        r"(?im)^domain\s*:\s*`?([a-z0-9._-]+)`?\s*$",
        r"(?im)^domain key\s*:\s*`?([a-z0-9._-]+)`?\s*$",
        r"(?im)^#\s*domain\s*:\s*([a-z0-9._-]+)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, domain_md_text)
        if match:
            return (match.group(1) or "").strip()
    return ""


def _find_upstream_requirements(inputs_dir: Path, max_items: int = 20) -> list[str]:
    if not inputs_dir.exists():
        return []
    matches: list[str] = []
    for candidate in inputs_dir.rglob("*"):
        if not candidate.is_file():
            continue
        name = candidate.name.lower()
        if name in {"requirements.yml", "requirements.md"}:
            matches.append(str(candidate))
        if len(matches) >= max_items:
            break
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(prog="detect_repo_context.py")
    parser.add_argument(
        "--root",
        default=".",
        help="Path to inspect (repo root by default).",
    )
    args = parser.parse_args()

    root = _repo_root((Path.cwd() / args.root).resolve())

    enterprise_md = root / "ENTERPRISE.md"
    solution_md = root / "SOLUTION.md"
    domain_md = root / "DOMAIN.md"
    inputs_dir = root / "inputs"

    has_enterprise = enterprise_md.exists()
    has_solution = solution_md.exists()
    has_domain = domain_md.exists()

    repo_type = "unknown"
    if has_domain:
        repo_type = "domain"
    elif has_solution:
        repo_type = "solution"
    elif has_enterprise:
        repo_type = "enterprise"

    domain_hint = _extract_domain_hint(_read_text(domain_md)) if has_domain else ""
    upstream_requirements = _find_upstream_requirements(inputs_dir)

    result = {
        "repo_root": str(root),
        "repo_type": repo_type,
        "has_enterprise_md": has_enterprise,
        "has_solution_md": has_solution,
        "has_domain_md": has_domain,
        "domain_hint": domain_hint,
        "inputs_dir_exists": inputs_dir.exists(),
        "upstream_requirement_files": upstream_requirements,
    }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
