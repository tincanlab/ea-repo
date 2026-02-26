#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def _ensure_common_python_on_path() -> None:
    common_python = Path(__file__).resolve().parents[2] / "common" / "python"
    common_python_str = str(common_python)
    if common_python_str not in sys.path:
        sys.path.insert(0, common_python_str)


_ensure_common_python_on_path()

from openarchitect_skill_common.repo_bootstrap import bootstrap_repos
from openarchitect_skill_common.initiative_selector import (
    build_selector_from_pipeline_path,
    load_yaml_payload,
    selector_payloads_equal,
)
from openarchitect_skill_common.structured_artifact_validation import validate_structured_artifacts


EA_REQUIRED_FILES: tuple[str, ...] = (
    "ENTERPRISE.md",
    "ROADMAP.md",
    "architecture/enterprise/target-architecture.yml",
    "architecture/enterprise/capability-map.yml",
    "architecture/enterprise/governance.yml",
    "architecture/enterprise/portfolio-assessment.yml",
    "architecture/portfolio/initiatives.yml",
)

EA_OPTIONAL_FILES: tuple[str, ...] = (
    "ROADMAP.yml",
    "architecture/portfolio/initiative-pipeline.yml",
)
EA_PIPELINE_FILE = "architecture/portfolio/initiative-pipeline.yml"
EA_SELECTOR_FILE = "architecture/portfolio/initiatives.yml"


class SyncError(RuntimeError):
    def __init__(self, message: str, *, exit_code: int = 3, detail: str | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.detail = detail


def _empty_repo_guidance() -> str:
    return (
        "Run the `enterprise-architecture` skill to initialize EA baseline artifacts "
        "(for example `ENTERPRISE.md`, `ROADMAP.md`, and `architecture/enterprise/*`), "
        "commit them to the EA repo, then rerun quick-start sync."
    )


def _repo_root(start: Path, *, require_git: bool = False) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    if require_git:
        raise ValueError(
            "No .git repository found from "
            f"`{current}` upward. Quick-start is Git-first. "
            "In containers, set OPENARCHITECT_GIT_WORKDIR to a cloned repo path "
            "or pass --root to a repo directory, then rerun."
        )
    return current


def _run_git_capture(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _redact_secrets(text: str) -> str:
    if not text:
        return text
    redacted = text
    redacted = re.sub(r"github_pat_[A-Za-z0-9_]+", "github_pat_***", redacted)
    redacted = re.sub(r"\bgh[pousr]_[A-Za-z0-9]+\b", "gh***", redacted)
    redacted = re.sub(r"https://([^/@\s:]+):([^@\s]+)@github\.com", r"https://***:***@github.com", redacted)
    redacted = re.sub(r"https://([^@\s]+)@github\.com", r"https://***@github.com", redacted)
    return redacted


def _redact_repo_url(repo_url: str) -> str:
    raw = str(repo_url or "").strip()
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return _redact_secrets(raw)
    if not parsed.netloc:
        return _redact_secrets(raw)
    if "@" not in parsed.netloc:
        return _redact_secrets(raw)
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    clean = urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))
    return _redact_secrets(clean)


def _classify_git_error(output: str) -> str:
    low = str(output or "").lower()
    if "repository is empty" in low:
        return "empty_repo"
    if "repository not found" in low or ("not found" in low and "repository" in low):
        return "not_found"
    if (
        "authentication failed" in low
        or "could not read username" in low
        or "permission denied" in low
        or "requires authentication" in low
        or "http basic: access denied" in low
        or "403" in low
        or "401" in low
    ):
        return "auth"
    if (
        "could not resolve host" in low
        or "name or service not known" in low
        or "failed to connect" in low
        or "operation timed out" in low
        or "timed out" in low
        or "network is unreachable" in low
        or "connection reset" in low
    ):
        return "network"
    return "unknown"


def _auth_source_label() -> str:
    if str(os.getenv("GITHUB_TOKEN", "")).strip():
        return "GITHUB_TOKEN"
    if str(os.getenv("GH_TOKEN", "")).strip():
        return "GH_TOKEN"
    if str(os.getenv("GIT_ASKPASS", "")).strip():
        return "GIT_ASKPASS"
    return "none"


def _raise_sync_error(*, action: str, repo_url: str, process: subprocess.CompletedProcess[str]) -> None:
    detail = _redact_secrets(str(process.stdout or "").strip())
    safe_repo_url = _redact_repo_url(repo_url)
    category = _classify_git_error(detail)
    if category == "empty_repo":
        raise SyncError(
            f"GitHub repo has no commits yet (empty repository): {safe_repo_url}. {_empty_repo_guidance()}",
            detail=detail,
        )
    if category == "not_found":
        raise SyncError(
            f"GitHub repo was not found or is not accessible: {safe_repo_url}. Verify owner/repo and access. If the repo does not exist yet, run the `repo-creation` skill to create it, then rerun quick-start.",
            detail=detail,
        )
    if category == "auth":
        raise SyncError(
            f"GitHub authentication failed while {action}: {safe_repo_url}. Set GITHUB_TOKEN/GH_TOKEN with repo access.",
            detail=detail,
        )
    if category == "network":
        raise SyncError(
            f"Network error while {action}: {safe_repo_url}. Check DNS/network/proxy and retry.",
            detail=detail,
        )
    raise SyncError(
        f"Git command failed while {action}: {safe_repo_url} (exit {process.returncode}).",
        detail=detail,
    )


def _normalize_profile(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"enterprise", "ea"}:
        return "ea"
    if normalized in {"solution", "sa"}:
        return "sa"
    if normalized in {"domain", "da"}:
        return "da"
    if normalized in {"developer", "dev"}:
        return "dev"
    if normalized in {"full", ""}:
        return "full"
    raise ValueError(f"Unsupported profile: {value}")


def _profile_from_args(args: argparse.Namespace) -> str:
    if str(args.profile or "").strip():
        return _normalize_profile(args.profile)
    container_role = str(os.getenv("OPENARCHITECT_CONTAINER_ROLE", "")).strip()
    if container_role:
        return _normalize_profile(container_role)
    return "full"


def _print_validation(root: Path, *, allow_partial: bool, no_drift: bool) -> int:
    result = validate_structured_artifacts(
        root=root,
        require_minimum=not allow_partial,
        check_drift=not no_drift,
    )

    print(f"Quick-start validation root: {root}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    for error in result.errors:
        print(f"ERROR: {error}")
    if result.ok:
        print("Validation passed.")
        return 0
    print(f"Validation failed with {len(result.errors)} error(s).")
    return 1


def _print_ea_validation(root: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    missing_required: list[str] = []

    for rel in EA_REQUIRED_FILES:
        path = root / rel
        if not path.exists():
            missing_required.append(rel)
            errors.append(f"Missing EA artifact: `{rel}`")
            continue
        if path.suffix.lower() in {".yml", ".yaml"}:
            try:
                import yaml

                with path.open("r", encoding="utf-8") as handle:
                    payload = yaml.safe_load(handle)
                if payload is None:
                    errors.append(f"EA artifact is empty YAML: `{rel}`")
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(f"EA artifact YAML parse failed `{rel}`: {exc}")

    for rel in EA_OPTIONAL_FILES:
        if not (root / rel).exists():
            warnings.append(f"Optional EA artifact not present: `{rel}`")

    pipeline_path = root / EA_PIPELINE_FILE
    selector_path = root / EA_SELECTOR_FILE
    if pipeline_path.exists():
        try:
            build = build_selector_from_pipeline_path(pipeline_path)
            for issue in build.errors:
                errors.append(f"Initiative pipeline issue: {issue}")
            if selector_path.exists():
                actual_selector = load_yaml_payload(selector_path)
                if not selector_payloads_equal(
                    expected_payload=build.payload,
                    actual_payload=actual_selector,
                ):
                    errors.append(
                        "Selector drift: `architecture/portfolio/initiatives.yml` is "
                        "out of sync with `architecture/portfolio/initiative-pipeline.yml`. "
                        "Regenerate with `python <skills_root>/enterprise-architecture/scripts/"
                        "generate_initiatives_selector.py --pipeline architecture/portfolio/"
                        "initiative-pipeline.yml --out architecture/portfolio/initiatives.yml`."
                    )
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"Initiative selector generation check failed: {exc}")
    else:
        warnings.append(
            "Optional EA source not present: "
            "`architecture/portfolio/initiative-pipeline.yml`."
        )

    print(f"Quick-start validation root: {root}")
    print("Validation profile: ea")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if not errors:
        print("EA validation passed.")
        return 0
    print(f"EA validation failed with {len(errors)} error(s).")
    if missing_required:
        if len(missing_required) == len(EA_REQUIRED_FILES):
            print(
                "HINT: EA baseline appears uninitialized. Run the `enterprise-architecture` skill to create baseline EA artifacts, commit them, then rerun quick-start."
            )
        else:
            print("HINT: Some EA artifacts are missing. Restore them from source control or regenerate via `enterprise-architecture`.")
    print(
        "HINT: Keep `architecture/portfolio/initiatives.yml` generated from "
        "`architecture/portfolio/initiative-pipeline.yml` to avoid routing drift."
    )
    print(
        "HINT: Configure `OPENARCHITECT_EA_REPO_URL` (or pass `--github-repo-url`) so EA quick-start can auto-hydrate missing files from GitHub."
    )
    return 1


def _resolve_repo_url(args: argparse.Namespace) -> str:
    url = str(args.github_repo_url or "").strip()
    if url:
        return url
    env_candidates = (
        "OPENARCHITECT_EA_REPO_URL",
        "OPENARCHITECT_GIT_REPO_URL",
        "OPENARCHITECT_REPO_URL",
    )
    for key in env_candidates:
        value = str(os.getenv(key, "")).strip()
        if value:
            return value
    raise ValueError(
        "github repo url is required for sync (pass --github-repo-url or set OPENARCHITECT_EA_REPO_URL/OPENARCHITECT_GIT_REPO_URL)."
    )


def _resolve_repo_url_optional(args: argparse.Namespace) -> str | None:
    try:
        return _resolve_repo_url(args)
    except ValueError:
        return None


def _normalize_optional_ref(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _check_remote_head(repo_url: str) -> str:
    probe = _run_git_capture(["git", "ls-remote", repo_url, "HEAD"])
    if probe.returncode != 0:
        _raise_sync_error(action="resolving remote HEAD", repo_url=repo_url, process=probe)
    output = str(probe.stdout or "").strip()
    if not output:
        raise SyncError(
            f"GitHub repo has no commits yet (empty repository): {_redact_repo_url(repo_url)}. {_empty_repo_guidance()}"
        )
    head_sha = output.split()[0].strip()
    if not head_sha:
        raise SyncError(
            f"Unable to parse remote HEAD SHA for repo: {_redact_repo_url(repo_url)}. Rerun with --debug for git output.",
            detail=_redact_secrets(output),
        )
    return head_sha


def _sync_ea_files_from_github(
    *,
    root: Path,
    repo_url: str,
    git_ref: str | None,
    dry_run: bool,
    fail_on_diff: bool,
    compare_only: bool = False,
) -> int:
    wanted = list(EA_REQUIRED_FILES + EA_OPTIONAL_FILES)
    mode = "compare" if compare_only else "sync"
    print(f"EA {mode} source repo: {_redact_repo_url(repo_url)}")
    print(f"EA {mode} auth source: {_auth_source_label()}")

    head_sha = _check_remote_head(repo_url)
    print(f"EA {mode} remote HEAD: {head_sha}")

    with tempfile.TemporaryDirectory(prefix="oa-ea-sync-") as tempdir:
        temp_root = Path(tempdir)
        clone_cmd = ["git", "clone", "--depth", "1", "--filter=blob:none", repo_url, str(temp_root)]
        clone = _run_git_capture(clone_cmd)
        if clone.returncode != 0:
            _raise_sync_error(action="cloning repo", repo_url=repo_url, process=clone)

        if git_ref:
            fetch = _run_git_capture(["git", "fetch", "--depth", "1", "origin", git_ref], cwd=temp_root)
            if fetch.returncode != 0:
                _raise_sync_error(
                    action=f"fetching ref `{git_ref}`",
                    repo_url=repo_url,
                    process=fetch,
                )
            checkout = _run_git_capture(["git", "checkout", "FETCH_HEAD"], cwd=temp_root)
            if checkout.returncode != 0:
                _raise_sync_error(
                    action=f"checking out fetched ref `{git_ref}`",
                    repo_url=repo_url,
                    process=checkout,
                )

        remote_sha_proc = _run_git_capture(["git", "rev-parse", "HEAD"], cwd=temp_root)
        if remote_sha_proc.returncode != 0:
            _raise_sync_error(action="reading fetched HEAD", repo_url=repo_url, process=remote_sha_proc)
        remote_sha = str(remote_sha_proc.stdout or "").strip()
        print(f"EA {mode} fetched ref: {remote_sha}")

        mismatches: list[str] = []
        missing_remote: list[str] = []
        copied: list[str] = []
        missing_local: list[str] = []
        matched: list[str] = []

        for rel in wanted:
            remote_path = temp_root / rel
            local_path = root / rel

            if not remote_path.exists():
                missing_remote.append(rel)
                continue

            remote_bytes = remote_path.read_bytes()
            if local_path.exists():
                local_bytes = local_path.read_bytes()
                if local_bytes != remote_bytes:
                    mismatches.append(rel)
                    print(f"REVIEW_REQUIRED: local differs from GitHub -> {rel}")
                else:
                    matched.append(rel)
                    print(f"COMPARE_OK: local matches GitHub -> {rel}")
                continue

            missing_local.append(rel)
            if compare_only:
                print(f"COMPARE_MISSING_LOCAL: {rel}")
                continue
            print(f"SYNC_MISSING_LOCAL: {rel}")
            copied.append(rel)
            if dry_run:
                continue
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(remote_bytes)

        for rel in missing_remote:
            print(f"WARNING: remote missing expected EA file: {rel}")

        if compare_only:
            print(
                f"EA compare summary: matched={len(matched)} mismatch={len(mismatches)} missing_local={len(missing_local)} missing_remote={len(missing_remote)}"
            )
        elif copied:
            action = "would copy" if dry_run else "copied"
            print(f"EA sync {action} {len(copied)} file(s).")

        if mismatches and fail_on_diff:
            print("ERROR: local files differ from GitHub and --fail-on-sync-diff is set.")
            return 2

    return 0


def main() -> int:
    default_root = Path(os.getenv("OPENARCHITECT_GIT_WORKDIR", "."))
    parser = argparse.ArgumentParser(
        prog="run_quick_start.py",
        description=(
            "Quick-start helper: run structured artifact validation and optionally "
            "bootstrap downstream repos."
        ),
    )
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument(
        "--profile",
        choices=["full", "ea", "sa", "da", "dev"],
        default=None,
        help="Validation profile. Default: OPENARCHITECT_CONTAINER_ROLE env or full.",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow missing canonical files; validate only discovered artifacts.",
    )
    parser.add_argument(
        "--no-drift",
        action="store_true",
        help="Run schema-only checks and skip cross-artifact drift checks.",
    )
    parser.add_argument(
        "--sync-from-github",
        action="store_true",
        help="EA profile only: fetch selected EA files from GitHub and hydrate missing local files.",
    )
    parser.add_argument(
        "--no-auto-compare",
        action="store_true",
        help="EA profile: disable automatic GitHub pre-validation fetch/compare during validation.",
    )
    parser.add_argument(
        "--github-repo-url",
        default=None,
        help="GitHub repo URL for EA sync. Falls back to OPENARCHITECT_EA_REPO_URL/OPENARCHITECT_GIT_REPO_URL.",
    )
    parser.add_argument(
        "--github-ref",
        default=None,
        help="Optional ref (branch/tag/sha) to fetch for EA sync.",
    )
    parser.add_argument(
        "--fail-on-sync-diff",
        action="store_true",
        help="Fail if local EA files differ from GitHub during compare/sync.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print traceback and raw git error output on failure.",
    )

    parser.add_argument("--bootstrap", action="store_true", help="Run downstream repo bootstrap after validation.")
    parser.add_argument("--solution-index", type=Path, default=Path("solution-index.yml"))
    parser.add_argument("--build-plan", type=Path, default=Path("architecture/solution/solution-build-plan.yml"))
    parser.add_argument("--workdir", type=Path, default=Path(".work/repos"))
    parser.add_argument("--solution-repo-root", type=Path, default=Path("."))
    parser.add_argument("--no-clone", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--snapshot-id", default=None)
    parser.add_argument("--upstream-repo-url", default=None)
    parser.add_argument("--upstream-commit", default=None)
    args = parser.parse_args()

    try:
        root = _repo_root((Path.cwd() / args.root).resolve(), require_git=True)
        profile = _profile_from_args(args)
        print(f"Quick-start profile: {profile}")

        if args.sync_from_github:
            if profile != "ea":
                print("ERROR: --sync-from-github currently supports --profile ea only.")
                return 2
            repo_url = _resolve_repo_url(args)
            sync_rc = _sync_ea_files_from_github(
                root=root,
                repo_url=repo_url,
                git_ref=_normalize_optional_ref(args.github_ref),
                dry_run=bool(args.dry_run),
                fail_on_diff=bool(args.fail_on_sync_diff),
            )
            if sync_rc != 0:
                return sync_rc
        elif profile == "ea" and not args.no_auto_compare:
            repo_url = _resolve_repo_url_optional(args)
            if repo_url:
                try:
                    sync_rc = _sync_ea_files_from_github(
                        root=root,
                        repo_url=repo_url,
                        git_ref=_normalize_optional_ref(args.github_ref),
                        dry_run=False,
                        fail_on_diff=bool(args.fail_on_sync_diff),
                        compare_only=False,
                    )
                    if sync_rc != 0:
                        return sync_rc
                except SyncError as exc:
                    # Bootstrap-friendly default: automatic EA pre-validation sync
                    # is best-effort so first-run environments can continue.
                    print(f"WARNING: EA auto-sync skipped: {exc}")
                    if args.debug and exc.detail:
                        print("DEBUG_GIT_OUTPUT:")
                        print(exc.detail)
                    elif exc.detail:
                        print("HINT: rerun with --debug to show raw git output.")
            else:
                print(
                    "INFO: EA GitHub sync/compare skipped (no repo URL configured). Set OPENARCHITECT_EA_REPO_URL or pass --github-repo-url."
                )

        if profile == "ea":
            validation_rc = _print_ea_validation(root)
        else:
            validation_rc = _print_validation(
                root,
                allow_partial=bool(args.allow_partial),
                no_drift=bool(args.no_drift),
            )

        if validation_rc != 0:
            return validation_rc

        if not args.bootstrap:
            return 0

        bootstrap_root = _repo_root((Path.cwd() / args.solution_repo_root).resolve(), require_git=True)
        return bootstrap_repos(
            solution_repo_root=bootstrap_root,
            solution_index_path=(Path.cwd() / args.solution_index).resolve(),
            build_plan_path=(Path.cwd() / args.build_plan).resolve(),
            workdir=(Path.cwd() / args.workdir).resolve(),
            no_clone=bool(args.no_clone),
            dry_run=bool(args.dry_run),
            snapshot_id=args.snapshot_id,
            upstream_repo_url=args.upstream_repo_url,
            upstream_commit=args.upstream_commit,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    except SyncError as exc:
        print(f"ERROR: {exc}")
        if args.debug and exc.detail:
            print("DEBUG_GIT_OUTPUT:")
            print(exc.detail)
        elif exc.detail:
            print("HINT: rerun with --debug to show raw git output.")
        return exc.exit_code
    except Exception as exc:  # pragma: no cover - defensive
        print(f"ERROR: quick-start failed unexpectedly: {exc}")
        if args.debug:
            traceback.print_exc()
        else:
            print("HINT: rerun with --debug for traceback.")
        return 99


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
