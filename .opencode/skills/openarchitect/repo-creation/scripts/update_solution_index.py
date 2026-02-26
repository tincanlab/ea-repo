from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _require_yaml():
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise RuntimeError("PyYAML is required (pip install pyyaml).") from exc
    return yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    yaml = _require_yaml()

    if not path.exists():
        raise FileNotFoundError(str(path))

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) if raw.strip() else {}
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping in {path}")
    return data


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    yaml = _require_yaml()

    text = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
        width=88,
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _ensure_list(obj: dict[str, Any], key: str) -> list[dict[str, Any]]:
    existing = obj.get(key)
    if existing is None:
        obj[key] = []
        return obj[key]  # type: ignore[return-value]
    if not isinstance(existing, list):
        raise ValueError(f"expected list for {key}")
    for item in existing:
        if not isinstance(item, dict):
            raise ValueError(f"expected list of mappings for {key}")
    return existing  # type: ignore[return-value]


def _infer_purpose(repo_key: str) -> str:
    key = _as_str(repo_key).lower()
    if key in {"solution_design", "solution"} or key.startswith("solution_design"):
        return "design"
    if key.startswith(("domain_", "oda_")):
        return "domain"
    if key.startswith(("api_", "tmf")):
        return "api"
    if key.startswith("infra_") or key.endswith("_infra"):
        return "infra"
    return "other"


def _default_entrypoints(*, repo_key: str, purpose: str) -> dict[str, str]:
    p = _as_str(purpose).lower()
    # Keep defaults minimal and repo-agnostic; repo skeletons can refine later.
    if repo_key == "solution_design" or p == "design":
        return {
            "solution_md": "SOLUTION.md",
            "agents_md": "AGENTS.md",
            "cascade_state": ".openarchitect/cascade-state.yml",
        }
    if p == "domain":
        return {
            "domain_md": "DOMAIN.md",
            "agents_md": "AGENTS.md",
            "cascade_state": ".openarchitect/cascade-state.yml",
        }
    return {
        "agents_md": "AGENTS.md",
        "cascade_state": ".openarchitect/cascade-state.yml",
    }


def _result_repo_url_index(result: dict[str, Any]) -> dict[tuple[str, str], str]:
    index: dict[tuple[str, str], str] = {}

    for item in result.get("created_repos") or []:
        if not isinstance(item, dict):
            continue
        owner = _as_str(item.get("owner")).lower()
        name = _as_str(item.get("name")).lower()
        url = _as_str(item.get("html_url"))
        if owner and name and url:
            index[(owner, name)] = url

    for item in result.get("mapped_repos") or []:
        if not isinstance(item, dict):
            continue
        owner = _as_str(item.get("owner")).lower()
        name = _as_str(item.get("name")).lower()
        url = _as_str(item.get("workspace_repo_url")) or _as_str(item.get("repo_url"))
        if owner and name and url:
            index.setdefault((owner, name), url)

    return index


def _result_success_set(result: dict[str, Any]) -> set[tuple[str, str]]:
    succeeded: set[tuple[str, str]] = set()

    for item in result.get("created_repos") or []:
        if not isinstance(item, dict):
            continue
        owner = _as_str(item.get("owner")).lower()
        name = _as_str(item.get("name")).lower()
        if owner and name:
            succeeded.add((owner, name))

    for item in result.get("mapped_repos") or []:
        if not isinstance(item, dict):
            continue
        owner = _as_str(item.get("owner")).lower()
        name = _as_str(item.get("name")).lower()
        if owner and name:
            succeeded.add((owner, name))

    return succeeded


def _result_failure_set(result: dict[str, Any]) -> set[tuple[str, str]]:
    failed: set[tuple[str, str]] = set()
    for item in result.get("failures") or []:
        if not isinstance(item, dict):
            continue
        owner = _as_str(item.get("owner")).lower()
        name = _as_str(item.get("name")).lower()
        if owner and name:
            failed.add((owner, name))
    return failed


def _upsert_repo_entry(
    *,
    repos: list[dict[str, Any]],
    repo_key: str,
    repo_url: str,
    purpose: str,
    description: str,
    entrypoints: dict[str, str],
) -> tuple[str, dict[str, Any]]:
    normalized_key = _as_str(repo_key)
    normalized_url = _as_str(repo_url)
    if not normalized_key:
        raise ValueError("repo_key is required")
    if not normalized_url:
        raise ValueError("repo_url is required")

    existing: dict[str, Any] | None = None
    for item in repos:
        if _as_str(item.get("repo_key")) == normalized_key:
            existing = item
            break

    if existing is None:
        created = {
            "repo_key": normalized_key,
            "repo_url": normalized_url,
            "purpose": _as_str(purpose) or "other",
            "entrypoints": dict(entrypoints),
        }
        if description.strip():
            created["description"] = description.strip()
        repos.append(created)
        return "created", created

    changed = False
    if _as_str(existing.get("repo_url")) != normalized_url:
        existing["repo_url"] = normalized_url
        changed = True

    if not _as_str(existing.get("purpose")) and _as_str(purpose):
        existing["purpose"] = _as_str(purpose)
        changed = True

    if description.strip() and not _as_str(existing.get("description")):
        existing["description"] = description.strip()
        changed = True

    existing_entrypoints = existing.get("entrypoints")
    if existing_entrypoints is None:
        existing["entrypoints"] = dict(entrypoints)
        changed = True
    elif isinstance(existing_entrypoints, dict):
        for k, v in entrypoints.items():
            if k not in existing_entrypoints:
                existing_entrypoints[k] = v
                changed = True
    else:
        raise ValueError(
            f"expected mapping for repo entrypoints (repo_key={normalized_key})"
        )

    return ("updated" if changed else "unchanged"), existing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Update repo-root solution-index.yml from a repo-creation request/result."
    )
    parser.add_argument("--solution-index", default="solution-index.yml")
    parser.add_argument(
        "--request", default="architecture/solution/repo-creation-request.yml"
    )
    parser.add_argument(
        "--result", default="architecture/solution/repo-creation-result.yml"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        solution_index_path = Path(args.solution_index)
        request_path = Path(args.request)
        result_path = Path(args.result)

        solution_index = _load_yaml(solution_index_path)
        request = _load_yaml(request_path)
        result = _load_yaml(result_path) if result_path.exists() else {}

        repos_requested = request.get("repos_requested")
        if not isinstance(repos_requested, list):
            raise ValueError("expected repos_requested[] in request YAML")

        repos = _ensure_list(solution_index, "repos")
        result_index = _result_repo_url_index(result)
        succeeded = _result_success_set(result)
        failed = _result_failure_set(result)

        actions: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for item in repos_requested:
            if not isinstance(item, dict):
                continue
            repo_key = _as_str(item.get("repo_key"))
            owner = _as_str(item.get("owner"))
            name = _as_str(item.get("name"))
            description = _as_str(item.get("description"))
            if not repo_key or not owner or not name:
                skipped.append({"reason": "missing_fields", "item": item})
                continue

            key = (owner.lower(), name.lower())
            if succeeded:
                if key not in succeeded:
                    skipped.append(
                        {
                            "reason": "not_in_result_success_set",
                            "repo_key": repo_key,
                            "owner": owner,
                            "name": name,
                        }
                    )
                    continue
            elif key in failed:
                skipped.append(
                    {
                        "reason": "in_result_failure_set",
                        "repo_key": repo_key,
                        "owner": owner,
                        "name": name,
                    }
                )
                continue

            resolved_url = result_index.get(key) or f"https://github.com/{owner}/{name}"

            purpose = _as_str(item.get("purpose")) or _infer_purpose(repo_key)
            action, entry = _upsert_repo_entry(
                repos=repos,
                repo_key=repo_key,
                repo_url=resolved_url,
                purpose=purpose,
                description=description,
                entrypoints=_default_entrypoints(repo_key=repo_key, purpose=purpose),
            )
            actions.append(
                {
                    "action": action,
                    "repo_key": repo_key,
                    "repo_url": resolved_url,
                    "purpose": purpose,
                    "entry": entry,
                }
            )

        payload: dict[str, Any] = {
            "ok": True,
            "dry_run": bool(args.dry_run),
            "solution_index_path": str(solution_index_path),
            "request_path": str(request_path),
            "result_path": str(result_path),
            "actions": actions,
            "skipped": skipped,
        }

        if args.dry_run:
            print(json.dumps(payload, ensure_ascii=True))
            return 0

        _write_yaml(solution_index_path, solution_index)
        print(json.dumps(payload, ensure_ascii=True))
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
        return 2
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
