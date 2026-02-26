from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .roadmap_sync import sync_roadmap


@dataclass(frozen=True)
class RepoSpec:
    repo_key: str
    kind: str
    domain_key: str | None
    oda_component: str | None


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.stdout.strip()


def _git_head_sha(repo_root: Path) -> str | None:
    try:
        return _run(["git", "rev-parse", "HEAD"], cwd=repo_root).strip()
    except Exception:
        return None


def _safe_write(path: Path, content: str, dry_run: bool) -> bool:
    if path.exists():
        return False
    if dry_run:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _read_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _resolve_domain_template_paths(solution_repo_root: Path) -> tuple[Path, Path]:
    package_openarchitect_root = Path(__file__).resolve().parents[3]
    env_root = str(os.getenv("OPENARCHITECT_SKILLS_ROOT", "")).strip()
    candidates: list[Path] = []
    if env_root:
        candidates.append(Path(env_root).resolve())
    candidates.append(solution_repo_root / ".codex" / "skills" / "openarchitect")
    candidates.append(package_openarchitect_root)

    for root in candidates:
        references = root / "domain-architecture" / "references"
        domain_template = references / "DOMAIN.md.template"
        roadmap_template = references / "ROADMAP.md.template"
        if domain_template.exists() and roadmap_template.exists():
            return domain_template, roadmap_template

    checked = ", ".join(str(root) for root in candidates)
    raise FileNotFoundError(
        "Missing domain templates. Checked skill roots: "
        + checked
    )


def _fill_placeholders(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"<{key}>", value)
    return rendered


def _repo_url_from_solution_index(solution_index: dict[str, Any], repo_key: str) -> str | None:
    for row in solution_index.get("repos", []) or []:
        if str(row.get("repo_key", "")).strip() == repo_key:
            url = str(row.get("repo_url", "")).strip()
            if url:
                return url
    return None


def _parse_build_plan(build_plan: dict[str, Any]) -> tuple[str, list[RepoSpec], dict[str, Any]]:
    solution_key = str(build_plan.get("solution_key", "")).strip()
    if not solution_key:
        raise ValueError("build plan missing `solution_key`")

    repos: list[RepoSpec] = []
    for row in build_plan.get("repos", []) or []:
        repo_key = str(row.get("repo_key", "")).strip()
        kind = str(row.get("kind", "")).strip()
        if not repo_key or not kind:
            continue
        repos.append(
            RepoSpec(
                repo_key=repo_key,
                kind=kind,
                domain_key=(str(row.get("domain_key")).strip() if row.get("domain_key") is not None else None),
                oda_component=(str(row.get("oda_component")).strip() if row.get("oda_component") is not None else None),
            )
        )
    if not repos:
        raise ValueError("build plan has no repos")

    bootstrap = build_plan.get("bootstrap") or {}
    if not isinstance(bootstrap, dict):
        bootstrap = {}

    return solution_key, repos, bootstrap


def _maybe_clone(repo_url: str, dest: Path, dry_run: bool) -> None:
    if dest.exists() and any(dest.iterdir()):
        return
    if dry_run:
        dest.mkdir(parents=True, exist_ok=True)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "clone", repo_url, str(dest)])


def _write_inputs_snapshot(
    *,
    repo_root: Path,
    solution_key: str,
    snapshot_id: str,
    upstream_repo_url: str | None,
    upstream_commit: str | None,
    upstream_roadmap_md: str | None,
    dry_run: bool,
) -> None:
    base = repo_root / "inputs" / "solution" / solution_key / snapshot_id
    source_yml = base / "source.yml"
    artifacts_dir = base / "artifacts"
    roadmap_copy = artifacts_dir / "ROADMAP.md"

    captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "upstream": {
            "type": "solution",
            "key": solution_key,
            "repo_url": upstream_repo_url or "",
            "commit": upstream_commit or "",
            "path": "ROADMAP.md",
        },
        "snapshot_id": snapshot_id,
        "captured_at": captured_at,
        "reason": "bootstrap_downstream_inputs",
    }
    _safe_write(source_yml, yaml.safe_dump(payload, sort_keys=False), dry_run=dry_run)
    if upstream_roadmap_md:
        _safe_write(roadmap_copy, upstream_roadmap_md, dry_run=dry_run)


def bootstrap_repos(
    *,
    solution_repo_root: Path,
    solution_index_path: Path,
    build_plan_path: Path,
    workdir: Path,
    no_clone: bool,
    dry_run: bool,
    snapshot_id: str | None,
    upstream_repo_url: str | None,
    upstream_commit: str | None,
) -> int:
    solution_index = _load_yaml(solution_index_path)
    build_plan = _load_yaml(build_plan_path)
    solution_key, repos, bootstrap_cfg = _parse_build_plan(build_plan)

    include_inputs = bool(bootstrap_cfg.get("include_solution_roadmap_in_downstream_inputs", True))
    create_entrypoints = bool(bootstrap_cfg.get("create_missing_entrypoints", True))

    upstream_roadmap_md = None
    roadmap_path = solution_repo_root / "ROADMAP.md"
    if include_inputs and roadmap_path.exists():
        upstream_roadmap_md = roadmap_path.read_text(encoding="utf-8")

    effective_repo_url = (
        upstream_repo_url
        or str(os.getenv("OPENARCHITECT_UPSTREAM_REPO_URL") or "").strip()
        or str(os.getenv("OPENARCHITECT_GIT_REPO_URL") or "").strip()
    )
    effective_commit = upstream_commit or _git_head_sha(solution_repo_root) or ""
    effective_snapshot = snapshot_id or (f"commit-{effective_commit[:12]}" if effective_commit else "snapshot-unknown")

    domain_template, domain_roadmap_template = _resolve_domain_template_paths(solution_repo_root)

    domain_md_tpl = _read_template(domain_template)
    domain_rm_tpl = _read_template(domain_roadmap_template)

    for spec in repos:
        repo_url = _repo_url_from_solution_index(solution_index, spec.repo_key) or ""
        repo_root = workdir / spec.repo_key

        if not no_clone and repo_url:
            _maybe_clone(repo_url, repo_root, dry_run=dry_run)
        else:
            repo_root.mkdir(parents=True, exist_ok=True)

        if create_entrypoints:
            agents_path = repo_root / "AGENTS.md"
            agents_text = (
                "# AGENTS\n\n"
                "This repo is part of a multi-repo solution.\n\n"
                "Start here:\n"
                "- `AGENTS.md` (this file)\n"
                "- `DOMAIN.md` (required for domain repos)\n"
                "- `ROADMAP.md` (expected)\n"
                "- `inputs/` (upstream snapshots)\n"
            )
            _safe_write(agents_path, agents_text, dry_run=dry_run)

            roadmap_md = repo_root / "ROADMAP.md"
            if spec.kind == "domain" and spec.domain_key:
                domain_values = {
                    "domain_key": spec.domain_key,
                    "oda_component_name_or_id": spec.oda_component or "",
                    "name or team": "TBD",
                }
                domain_md = _fill_placeholders(domain_md_tpl, domain_values)
                _safe_write(repo_root / "DOMAIN.md", domain_md, dry_run=dry_run)

                roadmap_md_text = _fill_placeholders(domain_rm_tpl, {"domain_key": spec.domain_key})
                _safe_write(roadmap_md, roadmap_md_text, dry_run=dry_run)

                if not dry_run and roadmap_md.exists():
                    try:
                        sync_roadmap(roadmap_md, repo_root / "ROADMAP.yml", check=False)
                    except Exception:
                        pass

        if include_inputs:
            _write_inputs_snapshot(
                repo_root=repo_root,
                solution_key=solution_key,
                snapshot_id=effective_snapshot,
                upstream_repo_url=effective_repo_url,
                upstream_commit=effective_commit,
                upstream_roadmap_md=upstream_roadmap_md,
                dry_run=dry_run,
            )

    return 0
