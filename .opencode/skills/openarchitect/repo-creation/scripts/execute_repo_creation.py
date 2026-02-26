from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _script_path(name: str) -> Path:
    return Path(__file__).resolve().parent / name


def _run_json_script(
    *, script_name: str, args: list[str]
) -> tuple[int, dict[str, Any]]:
    script = _script_path(script_name)
    cmd = [sys.executable, str(script), *args]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    output = _as_str(proc.stdout)
    if not output:
        payload = {
            "ok": False,
            "error": "script produced no JSON output",
            "stderr": _as_str(proc.stderr),
        }
        return proc.returncode, payload
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        parsed = {
            "ok": False,
            "error": "script output is not valid JSON",
            "stdout": output,
            "stderr": _as_str(proc.stderr),
        }
    if not isinstance(parsed, dict):
        parsed = {
            "ok": False,
            "error": "script JSON output is not an object",
            "stdout": output,
        }
    return proc.returncode, parsed


def _check_repo(
    *, owner: str, name: str, token_env: str
) -> tuple[bool, str, dict[str, Any]]:
    code, payload = _run_json_script(
        script_name="github_repo_check.py",
        args=["--owner", owner, "--repo", name, "--token-env", token_env],
    )
    if code != 0 or not bool(payload.get("ok")):
        return False, "", payload
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return (
            False,
            "",
            {"ok": False, "error": "missing check results", "payload": payload},
        )
    row = results[0]
    if not isinstance(row, dict):
        return (
            False,
            "",
            {"ok": False, "error": "invalid check result row", "payload": payload},
        )
    if bool(row.get("exists")):
        url = _as_str(row.get("html_url")) or f"https://github.com/{owner}/{name}"
        return True, url, payload
    return False, "", payload


def _create_repo(
    *,
    owner: str,
    name: str,
    description: str,
    visibility: str,
    token_env: str,
    dry_run: bool,
) -> tuple[bool, bool, str, dict[str, Any]]:
    args = [
        "--owner",
        owner,
        "--repo",
        name,
        "--description",
        description,
        "--token-env",
        token_env,
    ]
    if _as_str(visibility).lower() == "public":
        args.append("--public")
    else:
        args.append("--private")
    if dry_run:
        args.append("--dry-run")

    code, payload = _run_json_script(script_name="github_repo_create.py", args=args)
    if code != 0 or not bool(payload.get("ok")):
        return False, False, "", payload

    url = _as_str(payload.get("html_url")) or f"https://github.com/{owner}/{name}"
    created = bool(payload.get("created"))
    exists = bool(payload.get("exists"))
    return True, created, url, payload | {"exists": exists}


def _state_from_counts(*, total: int, successes: int, failures: int) -> str:
    if total == 0:
        return "completed"
    if failures == 0:
        return "completed"
    if successes == 0:
        return "failed"
    return "partial_failure"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Execute repo-creation request and update solution-index.yml."
    )
    parser.add_argument(
        "--request", default="architecture/solution/repo-creation-request.yml"
    )
    parser.add_argument(
        "--result", default="architecture/solution/repo-creation-result.yml"
    )
    parser.add_argument("--solution-index", default="solution-index.yml")
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--executed-by", default="repo-creation-script")
    parser.add_argument("--skip-solution-index-update", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    request_path = Path(args.request)
    result_path = Path(args.result)

    try:
        request = _load_yaml(request_path)
        repos_requested = request.get("repos_requested")
        if not isinstance(repos_requested, list):
            raise ValueError("expected repos_requested[] in request YAML")
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
        return 1

    request_id = _as_str(request.get("request_id")) or "repo-req-unknown"
    token = _as_str(os.getenv(args.token_env))

    created_repos: list[dict[str, Any]] = []
    mapped_repos: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    if not args.dry_run and not token:
        for item in repos_requested:
            if not isinstance(item, dict):
                continue
            failures.append(
                {
                    "owner": _as_str(item.get("owner")),
                    "name": _as_str(item.get("name")),
                    "step": "auth",
                    "error": f"missing token in env var {args.token_env}",
                }
            )
        result_payload: dict[str, Any] = {
            "request_id": request_id,
            "executed_at_utc": _utc_now(),
            "executed_by": args.executed_by,
            "execution": {"state": "blocked_no_credentials"},
            "created_repos": [],
            "mapped_repos": [],
            "failures": failures,
            "evidence": {"github_actions": evidence, "dry_run": False},
        }
        _write_yaml(result_path, result_payload)
        print(
            json.dumps(
                {
                    "ok": False,
                    "execution_state": "blocked_no_credentials",
                    "result_path": str(result_path),
                    "failures": len(failures),
                },
                ensure_ascii=True,
            )
        )
        return 2

    for item in repos_requested:
        if not isinstance(item, dict):
            continue
        repo_key = _as_str(item.get("repo_key"))
        owner = _as_str(item.get("owner"))
        name = _as_str(item.get("name"))
        description = _as_str(item.get("description"))
        action = _as_str(item.get("action")) or "create_then_map"
        visibility = _as_str(item.get("visibility")) or "private"
        is_default = bool(
            item.get("default_for_solution", item.get("default_for_workspace"))
        )

        if not owner or not name:
            failures.append(
                {
                    "owner": owner,
                    "name": name,
                    "step": "validate",
                    "error": "owner and name are required",
                }
            )
            continue

        if action == "map_only":
            if args.dry_run:
                repo_url = f"https://github.com/{owner}/{name}"
                mapped_repos.append(
                    {
                        "owner": owner,
                        "name": name,
                        "repo_url": repo_url,
                        "is_default": is_default,
                        "repo_key": repo_key,
                    }
                )
                evidence.append(
                    {
                        "repo_key": repo_key,
                        "owner": owner,
                        "name": name,
                        "action": "map_only",
                        "dry_run": True,
                        "status": "simulated",
                    }
                )
            else:
                exists, repo_url, check_payload = _check_repo(
                    owner=owner,
                    name=name,
                    token_env=args.token_env,
                )
                evidence.append(
                    {
                        "repo_key": repo_key,
                        "owner": owner,
                        "name": name,
                        "action": "map_only",
                        "dry_run": False,
                        "check": check_payload,
                    }
                )
                if not exists:
                    failures.append(
                        {
                            "owner": owner,
                            "name": name,
                            "step": "check",
                            "error": "repo does not exist or check failed",
                        }
                    )
                    continue
                mapped_repos.append(
                    {
                        "owner": owner,
                        "name": name,
                        "repo_url": repo_url,
                        "is_default": is_default,
                        "repo_key": repo_key,
                    }
                )
            continue

        if args.dry_run:
            repo_url = f"https://github.com/{owner}/{name}"
            evidence.append(
                {
                    "repo_key": repo_key,
                    "owner": owner,
                    "name": name,
                    "action": "create_then_map",
                    "dry_run": True,
                    "status": "simulated",
                }
            )
            mapped_repos.append(
                {
                    "owner": owner,
                    "name": name,
                    "repo_url": repo_url,
                    "is_default": is_default,
                    "repo_key": repo_key,
                }
            )
            continue

        ok, created, repo_url, create_payload = _create_repo(
            owner=owner,
            name=name,
            description=description,
            visibility=visibility,
            token_env=args.token_env,
            dry_run=False,
        )
        evidence.append(
            {
                "repo_key": repo_key,
                "owner": owner,
                "name": name,
                "action": "create_then_map",
                "dry_run": False,
                "create": create_payload,
            }
        )
        if not ok:
            failures.append(
                {
                    "owner": owner,
                    "name": name,
                    "step": "create",
                    "error": _as_str(create_payload.get("error")) or "create failed",
                }
            )
            continue
        if created:
            created_repos.append(
                {
                    "owner": owner,
                    "name": name,
                    "html_url": repo_url,
                    "repo_key": repo_key,
                }
            )
        mapped_repos.append(
            {
                "owner": owner,
                "name": name,
                "repo_url": repo_url,
                "is_default": is_default,
                "repo_key": repo_key,
            }
        )

    execution_state = _state_from_counts(
        total=len([r for r in repos_requested if isinstance(r, dict)]),
        successes=len(mapped_repos),
        failures=len(failures),
    )

    result_payload = {
        "request_id": request_id,
        "executed_at_utc": _utc_now(),
        "executed_by": args.executed_by,
        "execution": {"state": execution_state},
        "created_repos": created_repos,
        "mapped_repos": mapped_repos,
        "failures": failures,
        "evidence": {"github_actions": evidence, "dry_run": bool(args.dry_run)},
    }
    _write_yaml(result_path, result_payload)

    manifest_update: dict[str, Any] | None = None
    if not args.skip_solution_index_update:
        update_args = [
            "--solution-index",
            args.solution_index,
            "--request",
            args.request,
            "--result",
            args.result,
        ]
        if args.dry_run:
            update_args.append("--dry-run")
        update_code, update_payload = _run_json_script(
            script_name="update_solution_index.py",
            args=update_args,
        )
        manifest_update = {
            "exit_code": update_code,
            "payload": update_payload,
        }
        if update_code != 0 or not bool(update_payload.get("ok")):
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "solution-index update failed",
                        "execution_state": execution_state,
                        "result_path": str(result_path),
                        "manifest_update": manifest_update,
                    },
                    ensure_ascii=True,
                )
            )
            return 1

    print(
        json.dumps(
            {
                "ok": execution_state == "completed",
                "execution_state": execution_state,
                "result_path": str(result_path),
                "created_count": len(created_repos),
                "mapped_count": len(mapped_repos),
                "failure_count": len(failures),
                "manifest_update": manifest_update,
            },
            ensure_ascii=True,
        )
    )
    if execution_state == "completed":
        return 0
    if execution_state == "partial_failure":
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
