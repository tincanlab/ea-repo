#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"PyYAML is required for discovery: {exc}")


ACTIVE_STATUSES = {"active", "approved", "ready", "in_progress"}
DEFAULT_TRIGGER_STATUSES = ("approved", "ready", "in_progress")
ROLE_COMPOSE_FILES = {
    "sa": "docker-compose.sa.example.yml",
    "da": "docker-compose.domain.example.yml",
    "dev": "docker-compose.job.example.yml",
}
DEFAULT_LAUNCH_PORTS = {"sa": 4097, "da": 4098, "dev": 4099}
DEFAULT_WORKSTREAMS_CATALOG = "architecture/solution/domain-workstreams.yml"
KNOWN_ARTIFACTS = [
    "architecture/portfolio/initiative-pipeline.yml",
    "architecture/portfolio/initiatives.yml",
    "architecture/enterprise/domain-registry.yml",
    DEFAULT_WORKSTREAMS_CATALOG,
    "implementation-catalog.yml",
    "implementation-catalog.json",
    "solution-index.yml",
    "SOLUTION.md",
    "VISION.md",
    "ROADMAP.md",
]


def _is_placeholder(value: str) -> bool:
    text = str(value or "")
    return "__REQUIRED_" in text or "<" in text or ">" in text


def _normalize_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized or "active"


def _normalize_repo_url(url: str) -> str:
    value = str(url or "").strip()
    if value.endswith(".git"):
        value = value[:-4]
    return value


def _repo_slug(repo_url: str) -> str:
    text = _normalize_repo_url(repo_url)
    match = re.match(r"^https?://([^/]+)/([^/]+)/([^/]+)$", text)
    if not match:
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", text).strip("-")
        return safe or "repo"
    host, org, repo = match.groups()
    return f"{host}__{org}__{repo}"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"missing YAML file: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"failed to parse YAML {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be an object: {path}")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"missing JSON file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"failed to parse JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _load_implementation_catalog(path: Path) -> tuple[dict[str, Any], Path]:
    """Load implementation catalog, preferring YAML over JSON with sibling fallback."""
    resolved = path
    suffix = resolved.suffix.lower()
    if not resolved.exists():
        if suffix in (".yml", ".yaml"):
            json_fb = resolved.with_suffix(".json")
            if json_fb.exists():
                resolved = json_fb
        elif suffix == ".json":
            for yaml_ext in (".yml", ".yaml"):
                yaml_fb = resolved.with_suffix(yaml_ext)
                if yaml_fb.exists():
                    resolved = yaml_fb
                    break
    if not resolved.exists():
        raise ValueError(f"implementation catalog not found: {path}")
    resolved_suffix = resolved.suffix.lower()
    if resolved_suffix in (".yml", ".yaml"):
        payload = _load_yaml(resolved)
    else:
        payload = _load_json(resolved)
    return payload, resolved


def _load_env_file(path: Path, *, override: bool = False) -> int:
    if not path.exists():
        return 0
    loaded = 0
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if override or key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


def _status_is_active(status: Any, allow_inactive: bool) -> bool:
    if allow_inactive:
        return True
    normalized = _normalize_status(status)
    return normalized in ACTIVE_STATUSES


def _parse_status_set(raw_statuses: str) -> set[str]:
    parsed: set[str] = set()
    for item in str(raw_statuses or "").split(","):
        token = item.strip().lower()
        if token:
            parsed.add(token)
    return parsed


def _safe_token(value: str, fallback: str = "item", max_len: int = 40) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    if not normalized:
        normalized = fallback
    if len(normalized) > max_len:
        normalized = normalized[:max_len].rstrip("-")
    return normalized or fallback


def _resolve_output_path(path_value: str, workdir: Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = workdir / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_repo_relative_path(path_value: str, repo_root: Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = repo_root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _trim_text(text: str, max_chars: int = 2000) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[-max_chars:]


def _collect_top_level(path: Path, cap: int = 30) -> list[str]:
    if not path.exists():
        return []
    names = []
    for child in sorted(path.iterdir(), key=lambda item: item.name.lower()):
        if child.name == ".git":
            continue
        names.append(child.name)
        if len(names) >= cap:
            break
    return names


def _artifact_presence(repo_path: Path) -> dict[str, bool]:
    presence: dict[str, bool] = {}
    for rel in KNOWN_ARTIFACTS:
        presence[rel] = (repo_path / rel).exists()
    return presence


def _clone_repo(repo_url: str, dest: Path, github_token: str | None) -> None:
    repo_url = _normalize_repo_url(repo_url)
    if not repo_url:
        raise ValueError("repo_url is empty")
    if _is_placeholder(repo_url):
        raise ValueError(f"repo_url contains placeholder value: {repo_url}")
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1", "--filter=blob:none", repo_url, str(dest)]
    if github_token and repo_url.startswith("https://github.com/"):
        # Git over HTTPS with PAT should use Basic auth, not Bearer.
        basic_token = base64.b64encode(
            f"x-access-token:{github_token}".encode("utf-8")
        ).decode("ascii")
        cmd = [
            "git",
            "-c",
            f"http.extraHeader=Authorization: Basic {basic_token}",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            repo_url,
            str(dest),
        ]
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        if (
            repo_url.startswith("https://github.com/")
            and "repository not found" in stderr.lower()
            and not github_token
        ):
            raise ValueError(
                f"git clone failed for {repo_url}: repository not found or private repo "
                "(set GITHUB_TOKEN for private GitHub access)"
            )
        raise ValueError(f"git clone failed for {repo_url}: {stderr}")


def _parse_env_map(raw_env: Any) -> dict[str, str]:
    if isinstance(raw_env, dict):
        return {str(k): str(v) for k, v in raw_env.items()}
    if isinstance(raw_env, list):
        parsed: dict[str, str] = {}
        for item in raw_env:
            text = str(item)
            if "=" in text:
                key, value = text.split("=", 1)
                parsed[key.strip()] = value.strip()
            else:
                key = text.strip()
                if key:
                    parsed[key] = str(os.getenv(key) or "")
        return parsed
    return {}


def _infer_role(file_name: str, env_map: dict[str, str]) -> str:
    role = str(env_map.get("OPENARCHITECT_CONTAINER_ROLE") or "").strip().lower()
    if role:
        return role
    lower = file_name.lower()
    if ".ea." in lower:
        return "ea"
    if ".sa." in lower:
        return "sa"
    if ".domain." in lower or ".da." in lower:
        return "da"
    if ".job." in lower or ".dev." in lower:
        return "dev"
    return "unknown"


def _validate_compose_files(compose_root: Path) -> dict[str, Any]:
    files = sorted(compose_root.glob("docker-compose*.yml"))
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    for file_path in files:
        file_errors: list[str] = []
        file_warnings: list[str] = []
        role = "unknown"
        env_map: dict[str, str] = {}
        try:
            payload = yaml.safe_load(file_path.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict):
                raise ValueError("root is not an object")
            services = payload.get("services")
            if not isinstance(services, dict) or not services:
                raise ValueError("missing services block")
            if "opencode" in services and isinstance(services["opencode"], dict):
                svc = services["opencode"]
            else:
                first_service = next(iter(services.values()))
                if not isinstance(first_service, dict):
                    raise ValueError("service definition is not an object")
                svc = first_service
            env_map = _parse_env_map(svc.get("environment"))
            role = _infer_role(file_path.name, env_map)
        except Exception as exc:
            file_errors.append(f"parse error: {exc}")
            results.append(
                {
                    "file": str(file_path),
                    "role": role,
                    "env_keys": sorted(env_map.keys()),
                    "errors": file_errors,
                    "warnings": file_warnings,
                }
            )
            errors.append(f"{file_path.name}: parse error: {exc}")
            continue

        for key, value in env_map.items():
            if _is_placeholder(value):
                file_errors.append(f"{key} contains placeholder value '{value}'")

        if role == "ea":
            if not env_map.get("OPENARCHITECT_GIT_REPO_URL") and not env_map.get(
                "OPENARCHITECT_EA_REPO_URL"
            ):
                file_errors.append(
                    "ea requires OPENARCHITECT_GIT_REPO_URL or OPENARCHITECT_EA_REPO_URL"
                )
        elif role == "sa":
            for key in ("INITIATIVE_ID", "OPENARCHITECT_EA_REPO_URL"):
                if not str(env_map.get(key) or "").strip():
                    file_errors.append(f"sa requires {key}")
        elif role == "da":
            for key in ("WORKSTREAM_ID", "OPENARCHITECT_SA_REPO_URL"):
                if not str(env_map.get(key) or "").strip():
                    file_errors.append(f"da requires {key}")
        elif role == "dev":
            if (
                not str(env_map.get("WORK_ITEM_ID") or "").strip()
                and not str(env_map.get("API_ID") or "").strip()
            ):
                file_errors.append("dev requires WORK_ITEM_ID or API_ID")
        else:
            file_warnings.append("could not infer container role for compose file")

        results.append(
            {
                "file": str(file_path),
                "role": role,
                "env_keys": sorted(env_map.keys()),
                "errors": file_errors,
                "warnings": file_warnings,
            }
        )
        errors.extend([f"{file_path.name}: {item}" for item in file_errors])
        warnings.extend([f"{file_path.name}: {item}" for item in file_warnings])

    return {"files": results, "errors": errors, "warnings": warnings}


def _collect_selector_statuses(
    initiatives: list[dict[str, Any]],
    *,
    ea_repo_url: str,
    initiatives_catalog: str,
    default_implementation_catalog: str,
) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for initiative in initiatives:
        if not isinstance(initiative, dict):
            continue
        initiative_id = str(initiative.get("initiative_id") or "").strip()
        initiative_status = _normalize_status(initiative.get("status"))
        solution_repo_url = _normalize_repo_url(
            str(initiative.get("solution_repo_url") or "").strip()
        )
        if initiative_id:
            launch_env: dict[str, str] = {"INITIATIVE_ID": initiative_id}
            if ea_repo_url:
                launch_env["OPENARCHITECT_EA_REPO_URL"] = ea_repo_url
            if initiatives_catalog:
                launch_env["OPENARCHITECT_SELECTOR_CATALOG"] = initiatives_catalog
            entries[f"initiative:{initiative_id}"] = {
                "key": f"initiative:{initiative_id}",
                "kind": "initiative",
                "selector_id": initiative_id,
                "role": "sa",
                "status": initiative_status,
                "launch_env": launch_env,
            }

        workstreams = initiative.get("workstreams")
        if not isinstance(workstreams, list):
            continue
        for workstream in workstreams:
            if not isinstance(workstream, dict):
                continue
            workstream_id = str(workstream.get("workstream_id") or "").strip()
            workstream_status = _normalize_status(workstream.get("status"))
            workstream_repo_url = _normalize_repo_url(
                str(workstream.get("workstream_repo_url") or "").strip()
            )
            if workstream_id:
                launch_env = {"WORKSTREAM_ID": workstream_id}
                if solution_repo_url:
                    launch_env["OPENARCHITECT_SA_REPO_URL"] = solution_repo_url
                entries[f"workstream:{workstream_id}"] = {
                    "key": f"workstream:{workstream_id}",
                    "kind": "workstream",
                    "selector_id": workstream_id,
                    "role": "da",
                    "status": workstream_status,
                    "initiative_id": initiative_id,
                    "launch_env": launch_env,
                }

            jobs = workstream.get("jobs")
            if not isinstance(jobs, list):
                continue
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                work_item_id = str(job.get("work_item_id") or "").strip()
                api_id = str(job.get("api_id") or "").strip()
                selector_id = work_item_id or api_id or ""
                if not selector_id:
                    continue
                job_status = _normalize_status(job.get("status"))
                implementation_catalog_path = str(
                    job.get("implementation_catalog_path")
                    or default_implementation_catalog
                ).strip()
                launch_env = {}
                if work_item_id:
                    launch_env["WORK_ITEM_ID"] = work_item_id
                if api_id and not work_item_id:
                    launch_env["API_ID"] = api_id
                if implementation_catalog_path:
                    launch_env["OPENARCHITECT_SELECTOR_IMPLEMENTATION_CATALOG"] = (
                        implementation_catalog_path
                    )
                if workstream_repo_url:
                    launch_env["OPENARCHITECT_GIT_REPO_URL"] = workstream_repo_url
                entries[f"job:{selector_id}"] = {
                    "key": f"job:{selector_id}",
                    "kind": "job",
                    "selector_id": selector_id,
                    "role": "dev",
                    "status": job_status,
                    "workstream_id": workstream_id,
                    "initiative_id": initiative_id,
                    "launch_env": launch_env,
                }
    return entries


def _compute_status_changes(
    current_statuses: dict[str, dict[str, Any]],
    baseline_statuses: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    all_keys = sorted(set(current_statuses.keys()) | set(baseline_statuses.keys()))
    for key in all_keys:
        current = current_statuses.get(key)
        baseline = baseline_statuses.get(key)
        previous_status = (
            None if baseline is None else _normalize_status(baseline.get("status"))
        )
        next_status = (
            None if current is None else _normalize_status(current.get("status"))
        )
        if previous_status == next_status:
            continue
        change_type = "changed"
        if baseline is None:
            change_type = "added"
        elif current is None:
            change_type = "removed"
        source = current or baseline or {}
        changes.append(
            {
                "key": key,
                "kind": str(source.get("kind") or key.split(":", 1)[0]),
                "selector_id": str(source.get("selector_id") or key.split(":", 1)[-1]),
                "role": str(source.get("role") or ""),
                "change_type": change_type,
                "status_from": previous_status,
                "status_to": next_status,
            }
        )
    return changes


def _missing_launch_requirements(role: str, launch_env: dict[str, str]) -> list[str]:
    missing: list[str] = []
    if role == "sa":
        for key in ("INITIATIVE_ID", "OPENARCHITECT_EA_REPO_URL"):
            if not str(launch_env.get(key) or "").strip():
                missing.append(key)
    elif role == "da":
        for key in ("WORKSTREAM_ID", "OPENARCHITECT_SA_REPO_URL"):
            if not str(launch_env.get(key) or "").strip():
                missing.append(key)
    elif role == "dev":
        if (
            not str(launch_env.get("WORK_ITEM_ID") or "").strip()
            and not str(launch_env.get("API_ID") or "").strip()
        ):
            missing.append("WORK_ITEM_ID or API_ID")
    return missing


def _plan_launch_actions(
    current_statuses: dict[str, dict[str, Any]],
    baseline_statuses: dict[str, dict[str, Any]],
    *,
    trigger_statuses: set[str],
    launch_on_current: bool,
    launch_project_prefix: str,
    launch_ports: dict[str, int],
) -> list[dict[str, Any]]:
    counters: dict[str, int] = defaultdict(int)
    actions: list[dict[str, Any]] = []
    for key in sorted(current_statuses.keys()):
        current = current_statuses[key]
        role = str(current.get("role") or "").strip().lower()
        if role not in ROLE_COMPOSE_FILES:
            continue
        current_status = _normalize_status(current.get("status"))
        baseline = baseline_statuses.get(key)
        previous_status = (
            None if baseline is None else _normalize_status(baseline.get("status"))
        )
        if launch_on_current:
            should_launch = current_status in trigger_statuses
        else:
            should_launch = (
                current_status in trigger_statuses
                and previous_status != current_status
                and previous_status not in trigger_statuses
            )
        if not should_launch:
            continue

        index = counters[role]
        counters[role] += 1
        selector_token = _safe_token(str(current.get("selector_id") or key))
        project_name = f"{launch_project_prefix}-{role}-{selector_token}"
        if len(project_name) > 63:
            project_name = project_name[:63].rstrip("-")
        container_name = f"opencode-{role}-{selector_token}"
        if len(container_name) > 63:
            container_name = container_name[:63].rstrip("-")
        host_port = (
            int(launch_ports.get(role, DEFAULT_LAUNCH_PORTS.get(role, 4096))) + index
        )
        launch_env = {
            str(k): str(v) for k, v in (current.get("launch_env") or {}).items()
        }
        missing = _missing_launch_requirements(role, launch_env)

        actions.append(
            {
                "key": key,
                "kind": str(current.get("kind") or ""),
                "selector_id": str(current.get("selector_id") or ""),
                "role": role,
                "status_from": previous_status,
                "status_to": current_status,
                "project": project_name,
                "container_name": container_name,
                "host_port": host_port,
                "compose_file": ROLE_COMPOSE_FILES[role],
                "command": [
                    "docker",
                    "compose",
                    "-p",
                    project_name,
                    "-f",
                    "docker-compose.yml",
                    "-f",
                    ROLE_COMPOSE_FILES[role],
                    "up",
                    "-d",
                    "--build",
                ],
                "launch_env": launch_env,
                "missing_requirements": missing,
                "executed": False,
                "returncode": None,
                "output": "",
            }
        )
    return actions


def _execute_launch_actions(
    actions: list[dict[str, Any]], compose_root: Path
) -> tuple[int, int]:
    executed = 0
    failed = 0
    for action in actions:
        missing = action.get("missing_requirements") or []
        if missing:
            action["output"] = (
                f"Skipped: missing required launch env values ({', '.join(missing)})"
            )
            continue

        env = os.environ.copy()
        launch_env = {
            str(k): str(v) for k, v in (action.get("launch_env") or {}).items()
        }
        env.update(launch_env)
        env["HOST_PORT"] = str(action.get("host_port"))
        env["OPENCODE_CONTAINER_NAME"] = str(action.get("container_name") or "")
        proc = subprocess.run(
            action["command"],
            cwd=str(compose_root),
            env=env,
            capture_output=True,
            text=True,
        )
        executed += 1
        action["executed"] = True
        action["returncode"] = proc.returncode
        combined = (
            (proc.stdout or "")
            + ("\n" if proc.stdout and proc.stderr else "")
            + (proc.stderr or "")
        )
        action["output"] = _trim_text(combined)
        if proc.returncode != 0:
            failed += 1
    return executed, failed


def _to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Enterprise Repo Graph Discovery Report")
    lines.append("")
    lines.append(f"- Generated UTC: `{report['meta']['generated_at_utc']}`")
    lines.append(f"- EA repo URL: `{report['meta']['ea_repo_url']}`")
    if report["meta"].get("enterprise_id"):
        lines.append(f"- Enterprise ID: `{report['meta']['enterprise_id']}`")
    lines.append(f"- Workdir: `{report['meta']['workdir']}`")
    if "domain_registry_catalog" in report["meta"]:
        lines.append(
            f"- Domain registry catalog: `{report['meta']['domain_registry_catalog']}`"
        )
    if "domain_registry_loaded" in report["meta"]:
        lines.append(
            f"- Domain registry loaded: `{report['meta']['domain_registry_loaded']}`"
        )
    if "domain_registry_domain_count" in report["meta"]:
        lines.append(
            f"- Domain registry domains: `{report['meta']['domain_registry_domain_count']}`"
        )
    lines.append("")
    summary = report["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Repositories discovered: `{summary['repositories']}`")
    if "domains" in summary:
        lines.append(f"- Domains discovered: `{summary['domains']}`")
    lines.append(f"- Initiatives discovered: `{summary['initiatives']}`")
    lines.append(f"- workstreams discovered: `{summary['workstreams']}`")
    lines.append(f"- Jobs discovered: `{summary['jobs']}`")
    if "status_changes" in summary:
        lines.append(f"- Status changes: `{summary['status_changes']}`")
    if "launch_actions" in summary:
        lines.append(f"- Launch actions planned: `{summary['launch_actions']}`")
    if "launch_executed" in summary:
        lines.append(f"- Launch actions executed: `{summary['launch_executed']}`")
    if "launch_failed" in summary:
        lines.append(f"- Launch actions failed: `{summary['launch_failed']}`")
    lines.append(f"- Errors: `{summary['errors']}`")
    lines.append(f"- Warnings: `{summary['warnings']}`")
    lines.append("")
    lines.append("## Repositories")
    lines.append("")
    lines.append("| Repo URL | Roles | Key Artifacts Present |")
    lines.append("|---|---|---|")
    for repo in report["repositories"]:
        roles = ", ".join(repo["roles"]) or "-"
        artifact_count = sum(1 for value in repo["artifacts"].values() if value)
        lines.append(
            f"| `{repo['repo_url']}` | `{roles}` | `{artifact_count}/{len(KNOWN_ARTIFACTS)}` |"
        )
    lines.append("")
    status_tracking = report.get("status_tracking") or {}
    status_changes = status_tracking.get("changes") or []
    if status_tracking:
        lines.append("## Status Tracking")
        lines.append("")
        lines.append(
            f"- Trigger statuses: `{', '.join(status_tracking.get('trigger_statuses') or [])}`"
        )
        lines.append(
            f"- Current selectors tracked: `{status_tracking.get('current_selectors', 0)}`"
        )
        lines.append(
            f"- Baseline selectors tracked: `{status_tracking.get('baseline_selectors', 0)}`"
        )
        lines.append(f"- Changes detected: `{len(status_changes)}`")
        if status_tracking.get("baseline_json"):
            lines.append(f"- Baseline report: `{status_tracking['baseline_json']}`")
        lines.append("")
    if status_changes:
        lines.append("## Status Changes")
        lines.append("")
        lines.append("| Kind | Selector | Role | From | To | Type |")
        lines.append("|---|---|---|---|---|---|")
        for item in status_changes:
            lines.append(
                "| `{}` | `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                    item.get("kind") or "-",
                    item.get("selector_id") or "-",
                    item.get("role") or "-",
                    item.get("status_from") or "-",
                    item.get("status_to") or "-",
                    item.get("change_type") or "-",
                )
            )
        lines.append("")
    automation = report.get("automation") or {}
    actions = automation.get("planned_actions") or []
    if automation:
        lines.append("## Automation")
        lines.append("")
        lines.append(
            f"- Launch planning enabled: `{automation.get('plan_enabled', False)}`"
        )
        lines.append(
            f"- Launch execution enabled: `{automation.get('launch_enabled', False)}`"
        )
        lines.append(
            f"- Launch on current status: `{automation.get('launch_on_current', False)}`"
        )
        lines.append(f"- Planned actions: `{len(actions)}`")
        lines.append(f"- Executed actions: `{automation.get('executed', 0)}`")
        lines.append(f"- Failed actions: `{automation.get('failed', 0)}`")
        lines.append("")
    if actions:
        lines.append("### Planned Launches")
        lines.append("")
        lines.append("| Role | Selector | From | To | Port | Project | Result |")
        lines.append("|---|---|---|---|---|---|---|")
        for item in actions:
            result = "planned"
            if item.get("missing_requirements"):
                result = "skipped-missing-env"
            elif item.get("executed") and item.get("returncode", 1) != 0:
                result = "failed"
            elif item.get("executed"):
                result = "launched"
            lines.append(
                "| `{}` | `{}` | `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                    item.get("role") or "-",
                    item.get("selector_id") or "-",
                    item.get("status_from") or "-",
                    item.get("status_to") or "-",
                    item.get("host_port") if item.get("host_port") is not None else "-",
                    item.get("project") or "-",
                    result,
                )
            )
        lines.append("")
    lines.append("## Validation Findings")
    lines.append("")
    if report["validation"]["errors"]:
        lines.append("### Errors")
        lines.append("")
        for item in report["validation"]["errors"]:
            lines.append(f"- {item}")
        lines.append("")
    if report["validation"]["warnings"]:
        lines.append("### Warnings")
        lines.append("")
        for item in report["validation"]["warnings"]:
            lines.append(f"- {item}")
        lines.append("")
    if not report["validation"]["errors"] and not report["validation"]["warnings"]:
        lines.append("- No validation findings.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover selector-linked enterprise repos from an EA repo and validate key artifacts."
    )
    parser.add_argument(
        "--env-file",
        default="",
        help=(
            "Optional env file to load before discovery "
            "(defaults to OPENCODE_ENV_FILE, then .env.dev if present)."
        ),
    )
    parser.add_argument(
        "--ea-repo-url",
        required=True,
        help="EA source repo URL (contains initiatives catalog).",
    )
    parser.add_argument(
        "--initiatives-catalog",
        default="architecture/portfolio/initiatives.yml",
        help="EA initiatives catalog path (repo-relative).",
    )
    parser.add_argument(
        "--workstreams-catalog",
        dest="workstreams_catalog",
        default=DEFAULT_WORKSTREAMS_CATALOG,
        help="SA workstreams catalog path (repo-relative).",
    )
    parser.add_argument(
        "--domain-registry-catalog",
        default="architecture/enterprise/domain-registry.yml",
        help="EA domain registry path (repo-relative).",
    )
    parser.add_argument(
        "--implementation-catalog",
        default="implementation-catalog.yml",
        help="Default implementation catalog path in domain repos (repo-relative; auto-falls back to .json if .yml is absent).",
    )
    parser.add_argument(
        "--workdir",
        default=str(
            Path(__file__).resolve().parents[1] / ".tmp" / "enterprise-repo-graph"
        ),
        help="Local working directory for cloned repos and outputs.",
    )
    parser.add_argument(
        "--compose-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Directory containing docker-compose files for validation.",
    )
    parser.add_argument(
        "--allow-inactive",
        action="store_true",
        help="Include non-active selector entries.",
    )
    parser.add_argument(
        "--validate-compose",
        action="store_true",
        help="Validate docker-compose role files under --compose-root.",
    )
    parser.add_argument(
        "--output",
        choices=["json", "markdown", "both"],
        default="both",
        help="Report output format.",
    )
    parser.add_argument(
        "--json-out",
        default="enterprise-repo-graph.json",
        help="JSON output file name/path.",
    )
    parser.add_argument(
        "--markdown-out",
        default="enterprise-repo-graph.md",
        help="Markdown output file name/path.",
    )
    parser.add_argument(
        "--web-json-out",
        default="web/enterprise-repo-graph-viewer/enterprise-repo-graph.json",
        help="Repo-relative path where discovery JSON is published for the web viewer.",
    )
    parser.add_argument(
        "--clean-workdir",
        action="store_true",
        help="Delete workdir before discovery run.",
    )
    parser.add_argument(
        "--baseline-json",
        default=None,
        help="Optional previous discovery JSON report used for status-change detection.",
    )
    parser.add_argument(
        "--trigger-statuses",
        default=",".join(DEFAULT_TRIGGER_STATUSES),
        help="Comma-separated statuses that should trigger launch actions.",
    )
    parser.add_argument(
        "--plan-launches",
        action="store_true",
        help="Plan launch actions for selectors that match trigger-status rules.",
    )
    parser.add_argument(
        "--launch-containers",
        action="store_true",
        help="Execute planned docker compose launches for matching selectors.",
    )
    parser.add_argument(
        "--launch-compose-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Directory where docker compose files are located for launch execution.",
    )
    parser.add_argument(
        "--launch-project-prefix",
        default="opencode-auto",
        help="Project prefix used for auto-launched containers.",
    )
    parser.add_argument(
        "--launch-port-sa",
        type=int,
        default=DEFAULT_LAUNCH_PORTS["sa"],
        help="Base SA host port.",
    )
    parser.add_argument(
        "--launch-port-da",
        type=int,
        default=DEFAULT_LAUNCH_PORTS["da"],
        help="Base DA host port.",
    )
    parser.add_argument(
        "--launch-port-dev",
        type=int,
        default=DEFAULT_LAUNCH_PORTS["dev"],
        help="Base DEV host port.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    env_file_value = str(args.env_file or "").strip()
    if env_file_value:
        env_file_path = Path(env_file_value)
        if not env_file_path.is_absolute():
            env_file_path = repo_root / env_file_path
        _load_env_file(env_file_path)
    else:
        env_file_hint = str(os.getenv("OPENCODE_ENV_FILE") or "").strip()
        if env_file_hint:
            hinted_path = Path(env_file_hint)
            if not hinted_path.is_absolute():
                hinted_path = repo_root / hinted_path
            _load_env_file(hinted_path)
        else:
            default_env_dev = repo_root / ".env.dev"
            if default_env_dev.exists():
                _load_env_file(default_env_dev)

    workdir = Path(args.workdir).resolve()
    if args.clean_workdir and workdir.exists():
        shutil.rmtree(workdir)
    repos_dir = workdir / "repos"
    repos_dir.mkdir(parents=True, exist_ok=True)

    github_token = str(os.getenv("GITHUB_TOKEN") or "").strip() or None
    validation_errors: list[str] = []
    validation_warnings: list[str] = []
    trigger_statuses = _parse_status_set(args.trigger_statuses)
    if not trigger_statuses:
        trigger_statuses = set(DEFAULT_TRIGGER_STATUSES)
    launch_ports = {
        "sa": int(args.launch_port_sa),
        "da": int(args.launch_port_da),
        "dev": int(args.launch_port_dev),
    }
    launch_plan_enabled = bool(args.plan_launches or args.launch_containers)
    launch_compose_root = Path(args.launch_compose_root).resolve()
    baseline_statuses: dict[str, dict[str, Any]] = {}
    baseline_json_path: Path | None = None
    if args.baseline_json:
        baseline_json_path = Path(args.baseline_json).resolve()
        try:
            baseline_payload = _load_json(baseline_json_path)
            baseline_initiatives = baseline_payload.get("initiatives")
            if isinstance(baseline_initiatives, list):
                baseline_statuses = _collect_selector_statuses(
                    baseline_initiatives,
                    ea_repo_url=_normalize_repo_url(
                        str(baseline_payload.get("meta", {}).get("ea_repo_url") or "")
                    ),
                    initiatives_catalog=str(
                        baseline_payload.get("meta", {}).get("initiatives_catalog")
                        or "architecture/portfolio/initiatives.yml"
                    ),
                    default_implementation_catalog=str(
                        baseline_payload.get("meta", {}).get("implementation_catalog")
                        or args.implementation_catalog
                    ),
                )
            else:
                validation_warnings.append(
                    f"baseline report missing 'initiatives' list: {baseline_json_path}"
                )
                baseline_statuses = {}
        except ValueError as exc:
            baseline_statuses = {}
            validation_warnings.append(f"failed to load baseline report: {exc}")

    repo_cache: dict[str, Path] = {}
    repo_records: dict[str, dict[str, Any]] = {}
    initiatives_out: list[dict[str, Any]] = []
    domains_out: list[dict[str, Any]] = []
    workstreams_total = 0
    jobs_total = 0

    def ensure_repo(repo_url: str, role: str, source: str) -> Path | None:
        normalized = _normalize_repo_url(repo_url)
        if not normalized:
            validation_errors.append(f"{source}: missing repo URL for role={role}")
            return None
        if _is_placeholder(normalized):
            validation_errors.append(
                f"{source}: placeholder repo URL for role={role}: {normalized}"
            )
            return None

        if normalized in repo_cache:
            local_path = repo_cache[normalized]
        else:
            slug = _repo_slug(normalized)
            local_path = repos_dir / slug
            try:
                _clone_repo(normalized, local_path, github_token=github_token)
            except ValueError as exc:
                validation_errors.append(f"{source}: {exc}")
                return None
            repo_cache[normalized] = local_path

        record = repo_records.get(normalized)
        if record is None:
            artifacts = _artifact_presence(local_path)
            record = {
                "repo_url": normalized,
                "local_path": str(local_path),
                "roles": [role],
                "discovered_from": [source],
                "artifacts": artifacts,
                "top_level_entries": _collect_top_level(local_path),
            }
            repo_records[normalized] = record
        else:
            if role not in record["roles"]:
                record["roles"].append(role)
            if source not in record["discovered_from"]:
                record["discovered_from"].append(source)

        return local_path

    ea_path = ensure_repo(args.ea_repo_url, "ea_source", "entrypoint")
    if not ea_path:
        status_changes = _compute_status_changes({}, baseline_statuses)
        report = {
            "meta": {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "ea_repo_url": _normalize_repo_url(args.ea_repo_url),
                "enterprise_id": "",
                "workdir": str(workdir),
                "initiatives_catalog": args.initiatives_catalog,
                "workstreams_catalog": args.workstreams_catalog,
                "domain_registry_catalog": args.domain_registry_catalog,
                "implementation_catalog": args.implementation_catalog,
                "allow_inactive": bool(args.allow_inactive),
                "compose_validation_enabled": bool(args.validate_compose),
                "domain_registry_loaded": False,
                "domain_registry_domain_count": 0,
                "baseline_json": str(baseline_json_path)
                if baseline_json_path
                else None,
                "trigger_statuses": sorted(trigger_statuses),
                "launch_on_current": bool(True),
                "launch_enabled": bool(args.launch_containers),
                "launch_compose_root": str(launch_compose_root),
            },
            "summary": {
                "repositories": 0,
                "domains": 0,
                "initiatives": 0,
                "workstreams": 0,
                "jobs": 0,
                "status_changes": len(status_changes),
                "launch_actions": 0,
                "launch_executed": 0,
                "launch_failed": 0,
                "errors": len(validation_errors),
                "warnings": len(validation_warnings),
            },
            "repositories": [],
            "domains": [],
            "initiatives": [],
            "status_tracking": {
                "baseline_json": str(baseline_json_path)
                if baseline_json_path
                else None,
                "trigger_statuses": sorted(trigger_statuses),
                "current_selectors": 0,
                "baseline_selectors": len(baseline_statuses),
                "changes": status_changes,
            },
            "automation": {
                "plan_enabled": bool(launch_plan_enabled),
                "launch_enabled": bool(args.launch_containers),
                "launch_on_current": bool(True),
                "compose_root": str(launch_compose_root),
                "project_prefix": args.launch_project_prefix,
                "planned_actions": [],
                "executed": 0,
                "failed": 0,
            },
            "validation": {
                "errors": validation_errors,
                "warnings": validation_warnings,
                "compose": {"files": []},
            },
        }
        if args.output in ("json", "both"):
            json_out = _resolve_output_path(args.json_out, workdir)
            json_out.write_text(
                json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
            )
            print(f"Wrote JSON report: {json_out}")
            web_json_out = _resolve_repo_relative_path(args.web_json_out, repo_root)
            web_json_out.write_text(
                json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
            )
            print(f"Published web viewer JSON: {web_json_out}")
        if args.output in ("markdown", "both"):
            markdown_out = _resolve_output_path(args.markdown_out, workdir)
            markdown_out.write_text(_to_markdown(report), encoding="utf-8")
            print(f"Wrote Markdown report: {markdown_out}")
        return 2

    initiatives_path = ea_path / args.initiatives_catalog
    domain_registry_path = ea_path / args.domain_registry_catalog
    registry_domain_ids: set[str] = set()
    registry_loaded = False
    registry_enterprise_id = ""

    if domain_registry_path.exists():
        try:
            domain_registry_payload = _load_yaml(domain_registry_path)
            registry_enterprise_id = str(
                domain_registry_payload.get("enterprise_id") or ""
            ).strip()
            domains_rows = domain_registry_payload.get("domains")
            if not isinstance(domains_rows, list):
                validation_errors.append(
                    f"{domain_registry_path}: expected top-level 'domains' list"
                )
            else:
                registry_loaded = True
                for row in domains_rows:
                    if not isinstance(row, dict):
                        continue
                    domain_id = str(row.get("domain_id") or "").strip()
                    domain_status = _normalize_status(row.get("status"))
                    domain_name = str(row.get("name") or "").strip()
                    domain_owner = str(row.get("owner") or "").strip()
                    capabilities = row.get("capabilities")
                    capability_count = (
                        len(capabilities) if isinstance(capabilities, list) else 0
                    )
                    domains_out.append(
                        {
                            "domain_id": domain_id,
                            "name": domain_name,
                            "owner": domain_owner,
                            "status": domain_status,
                            "capability_count": capability_count,
                        }
                    )
                    if not domain_id:
                        validation_errors.append(
                            f"{domain_registry_path}: domain entry missing domain_id"
                        )
                        continue
                    if domain_id in registry_domain_ids:
                        validation_errors.append(
                            f"{domain_registry_path}: duplicate domain_id '{domain_id}'"
                        )
                        continue
                    registry_domain_ids.add(domain_id)
        except ValueError as exc:
            validation_errors.append(str(exc))
    else:
        validation_warnings.append(
            f"optional EA artifact not found: {domain_registry_path} (domain_id cross-reference checks skipped)"
        )
    try:
        initiatives_payload = _load_yaml(initiatives_path)
    except ValueError as exc:
        validation_errors.append(str(exc))
        initiatives_payload = {}

    initiatives_rows = initiatives_payload.get("initiatives")
    if not isinstance(initiatives_rows, list):
        validation_errors.append(
            f"{initiatives_path}: expected top-level 'initiatives' list"
        )
        initiatives_rows = []

    initiative_pipeline_descriptions: dict[str, str] = {}
    initiative_pipeline_path = (
        ea_path / "architecture" / "portfolio" / "initiative-pipeline.yml"
    )
    if initiative_pipeline_path.exists():
        try:
            initiative_pipeline_payload = _load_yaml(initiative_pipeline_path)
            pipeline_rows = initiative_pipeline_payload.get("initiatives")
            if isinstance(pipeline_rows, list):
                for pipeline_row in pipeline_rows:
                    if not isinstance(pipeline_row, dict):
                        continue
                    pipeline_id = str(pipeline_row.get("initiative_id") or "").strip()
                    pipeline_description = str(
                        pipeline_row.get("description") or ""
                    ).strip()
                    if pipeline_id and pipeline_description:
                        initiative_pipeline_descriptions[pipeline_id] = (
                            pipeline_description
                        )
        except ValueError as exc:
            validation_warnings.append(
                f"optional EA artifact invalid: {initiative_pipeline_path} ({exc})"
            )

    for row in initiatives_rows:
        if not isinstance(row, dict):
            continue
        initiative_id = str(row.get("initiative_id") or "").strip()
        initiative_name = str(row.get("name") or "").strip()
        metadata_obj = row.get("metadata")
        metadata_description = (
            str(metadata_obj.get("description") or "").strip()
            if isinstance(metadata_obj, dict)
            else ""
        )
        initiative_description = str(row.get("description") or "").strip()
        if not initiative_description:
            initiative_description = metadata_description
        if not initiative_description and initiative_id:
            initiative_description = initiative_pipeline_descriptions.get(
                initiative_id, ""
            )
        status = _normalize_status(row.get("status"))
        solution_repo_url = str(row.get("solution_repo_url") or "").strip()
        initiative_item: dict[str, Any] = {
            "initiative_id": initiative_id,
            "name": initiative_name,
            "description": initiative_description,
            "status": status,
            "solution_repo_url": _normalize_repo_url(solution_repo_url),
            "workstreams": [],
        }
        initiatives_out.append(initiative_item)
        source_key = f"initiative:{initiative_id or '<missing-id>'}"

        if not initiative_id:
            validation_errors.append(f"{source_key}: missing initiative_id")
        if not solution_repo_url:
            validation_errors.append(f"{source_key}: missing solution_repo_url")

        if not _status_is_active(status, args.allow_inactive):
            validation_warnings.append(
                f"{source_key}: skipped inactive initiative (status={status})"
            )
            continue

        solution_path = ensure_repo(solution_repo_url, "solution", source_key)
        if not solution_path:
            continue

        workstreams_rel_path = str(args.workstreams_catalog or "").strip()
        if not workstreams_rel_path:
            workstreams_rel_path = DEFAULT_WORKSTREAMS_CATALOG
        workstreams_path = solution_path / workstreams_rel_path
        if not workstreams_path.exists():
            validation_warnings.append(
                f"{source_key}: missing workstreams catalog {workstreams_path}"
            )
            continue

        try:
            workstreams_payload = _load_yaml(workstreams_path)
        except ValueError as exc:
            validation_errors.append(str(exc))
            continue
        workstreams_rows = workstreams_payload.get("workstreams")
        if not isinstance(workstreams_rows, list):
            validation_errors.append(
                f"{workstreams_path}: expected top-level 'workstreams' list"
            )
            continue

        for workstream in workstreams_rows:
            if not isinstance(workstream, dict):
                continue
            workstreams_total += 1
            workstream_id = str(workstream.get("workstream_id") or "").strip()
            workstream_status = _normalize_status(workstream.get("status"))
            workstream_repo_url = str(workstream.get("workstream_repo_url") or "").strip()
            workstream_initiative_id = str(
                workstream.get("initiative_id") or ""
            ).strip()
            domain_id = str(workstream.get("domain_id") or "").strip()
            handoff_ref = str(workstream.get("handoff_ref") or "").strip()
            workstream_item: dict[str, Any] = {
                "workstream_id": workstream_id,
                "status": workstream_status,
                "initiative_id": workstream_initiative_id,
                "domain_id": domain_id,
                "workstream_repo_url": _normalize_repo_url(workstream_repo_url),
                "handoff_ref": handoff_ref,
                "jobs": [],
            }
            initiative_item["workstreams"].append(workstream_item)
            workstream_source = (
                f"{source_key}/workstream:{workstream_id or '<missing-id>'}"
            )

            if not workstream_id:
                validation_errors.append(f"{workstream_source}: missing workstream_id")
            if (
                workstream_initiative_id
                and initiative_id
                and workstream_initiative_id != initiative_id
            ):
                validation_errors.append(
                    f"{workstream_source}: initiative_id mismatch ({workstream_initiative_id} != {initiative_id})"
                )
            if not domain_id:
                validation_errors.append(f"{workstream_source}: missing domain_id")
            elif registry_loaded and domain_id not in registry_domain_ids:
                validation_errors.append(
                    f"{workstream_source}: domain_id '{domain_id}' is not defined in {args.domain_registry_catalog}"
                )
            if not workstream_repo_url:
                validation_errors.append(
                    f"{workstream_source}: missing workstream_repo_url"
                )
                continue
            if not _status_is_active(workstream_status, args.allow_inactive):
                validation_warnings.append(
                    f"{workstream_source}: skipped inactive workstream (status={workstream_status})"
                )
                continue

            domain_path = ensure_repo(workstream_repo_url, "domain", workstream_source)
            if not domain_path:
                continue

            implementation_catalog_rel = str(
                workstream.get("implementation_catalog_path")
                or workstream.get("implementation_catalog")
                or workstream.get("implementation_catalog_file")
                or args.implementation_catalog
            ).strip()
            implementation_catalog_path = domain_path / implementation_catalog_rel
            if not implementation_catalog_path.exists():
                validation_warnings.append(
                    f"{workstream_source}: implementation catalog not found: {implementation_catalog_path}"
                )
                continue

            try:
                design_payload, implementation_catalog_path = _load_implementation_catalog(implementation_catalog_path)
            except ValueError as exc:
                validation_errors.append(str(exc))
                continue
            items_key = "work_items" if "work_items" in design_payload else "implementation_work_items"
            jobs = design_payload.get(items_key)
            if not isinstance(jobs, list):
                validation_warnings.append(
                    f"{workstream_source}: no work_items/implementation_work_items in {implementation_catalog_path}"
                )
                continue

            for job in jobs:
                if not isinstance(job, dict):
                    continue
                jobs_total += 1
                work_item_id = str(job.get("work_item_id") or "").strip()
                api_id = str(job.get("api_id") or "").strip()
                selector = work_item_id or api_id or "<missing-work-item-id>"
                job_status = _normalize_status(job.get("status"))
                implementation_repo_url = str(job.get("repo_url") or "").strip()
                repo_path = str(job.get("repo_path") or "").strip()
                job_item = {
                    "selector": selector,
                    "work_item_id": work_item_id,
                    "api_id": api_id,
                    "status": job_status,
                    "repo_url": _normalize_repo_url(implementation_repo_url),
                    "repo_path": repo_path,
                    "implementation_catalog_path": implementation_catalog_rel,
                }
                workstream_item["jobs"].append(job_item)
                job_source = f"{workstream_source}/job:{selector}"
                if not work_item_id and not api_id:
                    validation_errors.append(
                        f"{job_source}: missing work_item_id/api_id"
                    )

                if not _status_is_active(job_status, args.allow_inactive):
                    validation_warnings.append(
                        f"{job_source}: skipped inactive job (status={job_status})"
                    )
                    continue
                if implementation_repo_url:
                    ensure_repo(implementation_repo_url, "implementation", job_source)
                else:
                    validation_warnings.append(f"{job_source}: missing repo_url")

    compose_validation = {"files": [], "errors": [], "warnings": []}
    if args.validate_compose:
        compose_validation = _validate_compose_files(Path(args.compose_root).resolve())
        validation_errors.extend(compose_validation["errors"])
        validation_warnings.extend(compose_validation["warnings"])

    repositories = sorted(
        (
            {
                **record,
                "roles": sorted(record["roles"]),
                "discovered_from": sorted(record["discovered_from"]),
            }
            for record in repo_records.values()
        ),
        key=lambda item: item["repo_url"],
    )

    current_statuses = _collect_selector_statuses(
        initiatives_out,
        ea_repo_url=_normalize_repo_url(args.ea_repo_url),
        initiatives_catalog=args.initiatives_catalog,
        default_implementation_catalog=args.implementation_catalog,
    )
    status_changes = _compute_status_changes(current_statuses, baseline_statuses)

    planned_launches: list[dict[str, Any]] = []
    executed_launches = 0
    failed_launches = 0
    if launch_plan_enabled:
        if not baseline_statuses and not True:
            validation_warnings.append(
                "launch planning without baseline report may trigger all selectors in target statuses; "
                "use --baseline-json for transition-only behavior."
            )
        planned_launches = _plan_launch_actions(
            current_statuses,
            baseline_statuses,
            trigger_statuses=trigger_statuses,
            launch_on_current=bool(True),
            launch_project_prefix=_safe_token(
                args.launch_project_prefix, fallback="opencode-auto", max_len=24
            ),
            launch_ports=launch_ports,
        )
        if args.launch_containers:
            if not launch_compose_root.exists():
                validation_errors.append(
                    f"launch compose root not found: {launch_compose_root}"
                )
            else:
                executed_launches, failed_launches = _execute_launch_actions(
                    planned_launches, launch_compose_root
                )
                for action in planned_launches:
                    if (
                        action.get("executed")
                        and int(action.get("returncode") or 0) != 0
                    ):
                        validation_errors.append(
                            f"launch failed ({action.get('role')}:{action.get('selector_id')}): "
                            f"docker compose exited with code {action.get('returncode')}"
                        )

    report = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "ea_repo_url": _normalize_repo_url(args.ea_repo_url),
            "enterprise_id": registry_enterprise_id,
            "workdir": str(workdir),
            "initiatives_catalog": args.initiatives_catalog,
            "workstreams_catalog": args.workstreams_catalog,
            "domain_registry_catalog": args.domain_registry_catalog,
            "implementation_catalog": args.implementation_catalog,
            "allow_inactive": bool(args.allow_inactive),
            "compose_validation_enabled": bool(args.validate_compose),
            "domain_registry_loaded": bool(registry_loaded),
            "domain_registry_domain_count": len(registry_domain_ids),
            "baseline_json": str(baseline_json_path) if baseline_json_path else None,
            "trigger_statuses": sorted(trigger_statuses),
            "launch_on_current": bool(True),
            "launch_enabled": bool(args.launch_containers),
            "launch_compose_root": str(launch_compose_root),
        },
        "summary": {
            "repositories": len(repositories),
            "domains": len(domains_out),
            "initiatives": len(initiatives_out),
            "workstreams": workstreams_total,
            "jobs": jobs_total,
            "status_changes": len(status_changes),
            "launch_actions": len(planned_launches),
            "launch_executed": executed_launches,
            "launch_failed": failed_launches,
            "errors": len(validation_errors),
            "warnings": len(validation_warnings),
        },
        "repositories": repositories,
        "domains": domains_out,
        "initiatives": initiatives_out,
        "status_tracking": {
            "baseline_json": str(baseline_json_path) if baseline_json_path else None,
            "trigger_statuses": sorted(trigger_statuses),
            "current_selectors": len(current_statuses),
            "baseline_selectors": len(baseline_statuses),
            "changes": status_changes,
        },
        "automation": {
            "plan_enabled": bool(launch_plan_enabled),
            "launch_enabled": bool(args.launch_containers),
            "launch_on_current": bool(True),
            "compose_root": str(launch_compose_root),
            "project_prefix": _safe_token(
                args.launch_project_prefix, fallback="opencode-auto", max_len=24
            ),
            "planned_actions": planned_launches,
            "executed": executed_launches,
            "failed": failed_launches,
        },
        "validation": {
            "errors": validation_errors,
            "warnings": validation_warnings,
            "compose": compose_validation,
        },
    }

    if args.output in ("json", "both"):
        json_out = _resolve_output_path(args.json_out, workdir)
        json_out.write_text(
            json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Wrote JSON report: {json_out}")
        web_json_out = _resolve_repo_relative_path(args.web_json_out, repo_root)
        web_json_out.write_text(
            json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Published web viewer JSON: {web_json_out}")

    if args.output in ("markdown", "both"):
        markdown_out = _resolve_output_path(args.markdown_out, workdir)
        markdown_out.write_text(_to_markdown(report), encoding="utf-8")
        print(f"Wrote Markdown report: {markdown_out}")

    if validation_errors:
        print(f"Discovery completed with {len(validation_errors)} error(s).")
        return 2
    print("Discovery completed without validation errors.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())




