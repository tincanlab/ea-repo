#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _parse_last_json(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        payload = json.loads(lines[-1])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _run_json(cmd: list[str]) -> dict:
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = _parse_last_json(completed.stdout or "")
    if payload is None:
        raise ValueError(f"expected JSON output from command: {' '.join(cmd)}")
    return payload


def _run_text(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=str(cwd))


def _repo_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _git_reminder(pipeline: Path, out: Path) -> None:
    print("Reminder: commit and push selector updates to GitHub.")
    print(f"  git add {pipeline.as_posix()} {out.as_posix()}")
    print('  git commit -m "portfolio: update initiative pipeline and selector"')
    print("  git push")


def _auto_git_push(*, pipeline: Path, out: Path, message: str) -> int:
    root = _repo_root(Path.cwd())
    if root is None:
        print("ERROR: --auto-git-push requested but current directory is not inside a git repository.")
        return 2

    add = _run_text(["git", "add", str(pipeline), str(out)], cwd=root)
    if add.returncode != 0:
        print("ERROR: git add failed.")
        output = (add.stdout or "") + (add.stderr or "")
        if output.strip():
            print(output.strip())
        return 2

    commit = _run_text(["git", "commit", "-m", message], cwd=root)
    if commit.returncode != 0:
        output = (commit.stdout or "") + (commit.stderr or "")
        if "nothing to commit" in output.lower():
            print("Auto git push: no changes to commit.")
            return 0
        print("ERROR: git commit failed.")
        if output.strip():
            print(output.strip())
        return 2

    push = _run_text(["git", "push"], cwd=root)
    if push.returncode != 0:
        print("ERROR: git push failed.")
        output = (push.stdout or "") + (push.stderr or "")
        if output.strip():
            print(output.strip())
        return 2

    print("Auto git push completed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Upsert initiative into initiative-pipeline.yml and regenerate initiatives.yml "
            "in one command."
        )
    )
    parser.add_argument(
        "--pipeline",
        default="architecture/portfolio/initiative-pipeline.yml",
        help="Path to initiative-pipeline.yml",
    )
    parser.add_argument(
        "--out",
        default="architecture/portfolio/initiatives.yml",
        help="Path to generated initiatives.yml",
    )
    parser.add_argument("--initiative-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument(
        "--objective",
        action="append",
        default=[],
        help="Repeatable objective line; provide at least one.",
    )
    parser.add_argument(
        "--objectives-json",
        default="[]",
        help='Optional JSON array of objective strings merged with --objective.',
    )
    parser.add_argument("--business-case-id")
    parser.add_argument("--business-sponsor")
    parser.add_argument("--pm-owner")
    parser.add_argument("--it-owner")
    parser.add_argument("--t-shirt-size")
    parser.add_argument("--roi-band")
    parser.add_argument("--solution-repo-url")
    parser.add_argument("--publish-to-selector", default="false")
    parser.add_argument("--selector-status", default="planned")
    parser.add_argument("--metadata-json", default="{}")
    parser.add_argument(
        "--auto-git-push",
        action="store_true",
        help="Automatically git add/commit/push pipeline and selector files after successful generation.",
    )
    parser.add_argument(
        "--git-commit-message",
        default="portfolio: update initiative pipeline and selector",
        help="Commit message used with --auto-git-push.",
    )
    parser.add_argument(
        "--no-git-reminder",
        action="store_true",
        help="Suppress commit/push reminder output.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Pass through to selector generation.",
    )
    args = parser.parse_args(argv)

    pipeline_path = Path(args.pipeline).resolve()
    out_path = Path(args.out).resolve()
    scripts_dir = Path(__file__).resolve().parent
    upsert_script = scripts_dir / "upsert_initiative_pipeline.py"
    generator_script = (
        scripts_dir.parent.parent / "enterprise-architecture" / "scripts" / "generate_initiatives_selector.py"
    )

    upsert_cmd = [
        sys.executable,
        str(upsert_script),
        "--pipeline",
        str(pipeline_path),
        "--initiative-id",
        args.initiative_id,
        "--name",
        args.name,
        "--stage",
        args.stage,
        "--description",
        args.description,
        "--objectives-json",
        args.objectives_json,
        "--publish-to-selector",
        args.publish_to_selector,
        "--selector-status",
        args.selector_status,
        "--metadata-json",
        args.metadata_json,
    ]
    optional_fields = {
        "--business-case-id": args.business_case_id,
        "--business-sponsor": args.business_sponsor,
        "--pm-owner": args.pm_owner,
        "--it-owner": args.it_owner,
        "--t-shirt-size": args.t_shirt_size,
        "--roi-band": args.roi_band,
        "--solution-repo-url": args.solution_repo_url,
    }
    for flag, value in optional_fields.items():
        if value:
            upsert_cmd.extend([flag, value])
    for objective in args.objective:
        text = str(objective or "").strip()
        if text:
            upsert_cmd.extend(["--objective", text])

    gen_cmd = [
        sys.executable,
        str(generator_script),
        "--pipeline",
        str(pipeline_path),
        "--out",
        str(out_path),
    ]
    if args.allow_empty:
        gen_cmd.append("--allow-empty")

    try:
        upsert_payload = _run_json(upsert_cmd)
    except subprocess.CalledProcessError as exc:
        return int(exc.returncode or 1)

    initiative_id = str(upsert_payload.get("initiative_id") or args.initiative_id).strip()
    publish = bool(upsert_payload.get("publish_to_selector"))
    created = bool(upsert_payload.get("created"))
    action = "added" if created else "updated"
    print(f"{initiative_id} was {action} in initiative-pipeline.yml.")

    try:
        selector_payload = _run_json(gen_cmd)
    except subprocess.CalledProcessError as exc:
        error_payload = _parse_last_json(exc.stdout or "")
        details = error_payload.get("details") if isinstance(error_payload, dict) else []
        if not isinstance(details, list):
            details = []
        missing_repo_url = any(
            "publish_to_selector=true requires solution_repo_url" in str(item) for item in details
        )
        if publish and missing_repo_url:
            print(
                f"{initiative_id} was added to initiative-pipeline.yml, but not yet published to initiatives.yml."
            )
            print("Reason: publish_to_selector=true requires solution_repo_url.")
            print("Next: create/map the solution repo and set solution_repo_url, then regenerate initiatives.yml.")
            return int(exc.returncode or 1)
        return int(exc.returncode or 1)

    try:
        selected_ids = selector_payload.get("selected_ids")
        if not isinstance(selected_ids, list):
            selected_ids = []

        if publish:
            in_selector = initiative_id in [str(item).strip() for item in selected_ids]
            if in_selector:
                print(f"{initiative_id} was published to initiatives.yml.")
                print("Next: start SA container with:")
                print(f"  start-containers.bat sa {initiative_id} 4197")
                print("Or direct compose (worker_container):")
                print("  INITIATIVE_ID=<initiative_id> OPENARCHITECT_EA_REPO_URL=<ea-repo-url> docker compose -p opencode-sa-<initiative_id> -f docker-compose.yml -f docker-compose.sa.example.yml up -d --build")
            else:
                print(
                    f"{initiative_id} is marked publish_to_selector=true, but was not found in initiatives.yml."
                )
        else:
            print(
                f"{initiative_id} was added to initiative-pipeline.yml, but not yet published to initiatives.yml."
            )
        if args.auto_git_push:
            rc = _auto_git_push(
                pipeline=pipeline_path,
                out=out_path,
                message=str(args.git_commit_message or "").strip()
                or "portfolio: update initiative pipeline and selector",
            )
            if rc != 0:
                return rc
        elif not args.no_git_reminder:
            _git_reminder(pipeline_path, out_path)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
