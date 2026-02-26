#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=False)


def _normalize_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text or "unknown"


def _queue_state_from_action(action: dict[str, Any]) -> str:
    missing = action.get("missing_requirements")
    missing_list = missing if isinstance(missing, list) else []
    if missing_list:
        return "skipped"
    executed = bool(action.get("executed"))
    returncode = int(action.get("returncode") or 0) if executed else None
    if not executed:
        return "ready"
    if returncode == 0:
        return "launched"
    return "failed"


def _container_state_from_action(action: dict[str, Any]) -> str:
    queue_state = _queue_state_from_action(action)
    if queue_state == "launched":
        return "running"
    if queue_state == "failed":
        return "launch_failed"
    if queue_state == "skipped":
        return "skipped"
    return "unknown"


def _selector_key_for_action(action: dict[str, Any]) -> str:
    key = str(action.get("key") or "").strip()
    if key:
        return key
    role = str(action.get("role") or "").strip().lower()
    selector_id = str(action.get("selector_id") or "").strip()
    kind = "initiative"
    if role == "da":
        kind = "engagement"
    elif role == "dev":
        kind = "job"
    return f"{kind}:{selector_id or 'unknown'}"


def _extract_selectors(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    initiatives = report.get("initiatives")
    if not isinstance(initiatives, list):
        return rows

    for initiative in initiatives:
        if not isinstance(initiative, dict):
            continue
        initiative_id = str(initiative.get("initiative_id") or "").strip()
        if initiative_id:
            rows.append(
                {
                    "selector_key": f"initiative:{initiative_id}",
                    "kind": "initiative",
                    "role": "sa",
                    "selector_id": initiative_id,
                    "status": _normalize_status(initiative.get("status")),
                    "repo_url": str(initiative.get("solution_repo_url") or "").strip(),
                    "launch_env": {"INITIATIVE_ID": initiative_id},
                }
            )

        engagements = initiative.get("engagements")
        if not isinstance(engagements, list):
            continue
        for engagement in engagements:
            if not isinstance(engagement, dict):
                continue
            engagement_id = str(engagement.get("engagement_id") or "").strip()
            if engagement_id:
                rows.append(
                    {
                        "selector_key": f"engagement:{engagement_id}",
                        "kind": "engagement",
                        "role": "da",
                        "selector_id": engagement_id,
                        "status": _normalize_status(engagement.get("status")),
                        "repo_url": str(
                            engagement.get("domain_repo_url") or ""
                        ).strip(),
                        "launch_env": {"ENGAGEMENT_ID": engagement_id},
                    }
                )

            jobs = engagement.get("jobs")
            if not isinstance(jobs, list):
                continue
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                selector = (
                    str(job.get("selector") or "").strip()
                    or str(job.get("work_item_id") or "").strip()
                    or str(job.get("api_id") or "").strip()
                )
                if not selector:
                    continue
                launch_env: dict[str, str] = {}
                work_item_id = str(job.get("work_item_id") or "").strip()
                api_id = str(job.get("api_id") or "").strip()
                if work_item_id:
                    launch_env["WORK_ITEM_ID"] = work_item_id
                elif api_id:
                    launch_env["API_ID"] = api_id
                rows.append(
                    {
                        "selector_key": f"job:{selector}",
                        "kind": "job",
                        "role": "dev",
                        "selector_id": selector,
                        "status": _normalize_status(job.get("status")),
                        "repo_url": str(job.get("repo_url") or "").strip(),
                        "launch_env": launch_env,
                    }
                )
    return rows


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;

        CREATE TABLE IF NOT EXISTS selectors (
          selector_key TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          role TEXT NOT NULL,
          selector_id TEXT NOT NULL,
          status TEXT NOT NULL,
          repo_url TEXT,
          launch_env_json TEXT NOT NULL,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          source_run_id TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS selector_transitions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          selector_key TEXT NOT NULL,
          status_from TEXT,
          status_to TEXT,
          transition_type TEXT NOT NULL,
          observed_at TEXT NOT NULL,
          run_id TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_selector_transitions_key_time
          ON selector_transitions(selector_key, observed_at);

        CREATE TABLE IF NOT EXISTS launch_queue (
          queue_id TEXT PRIMARY KEY,
          selector_key TEXT NOT NULL,
          role TEXT NOT NULL,
          selector_id TEXT NOT NULL,
          trigger_status TEXT NOT NULL,
          state TEXT NOT NULL,
          reason TEXT,
          compose_project TEXT,
          compose_file TEXT,
          host_port INTEGER,
          launch_env_json TEXT NOT NULL,
          planned_at TEXT NOT NULL,
          claimed_at TEXT,
          completed_at TEXT,
          run_id TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_launch_queue_state ON launch_queue(state);
        CREATE INDEX IF NOT EXISTS idx_launch_queue_selector ON launch_queue(selector_key);

        CREATE TABLE IF NOT EXISTS containers (
          selector_key TEXT PRIMARY KEY,
          role TEXT NOT NULL,
          selector_id TEXT NOT NULL,
          compose_project TEXT NOT NULL,
          container_name TEXT,
          host_port INTEGER,
          runtime_state TEXT NOT NULL,
          started_at TEXT,
          updated_at TEXT NOT NULL,
          last_exit_code INTEGER,
          last_error TEXT
        );

        CREATE TABLE IF NOT EXISTS runs (
          run_id TEXT PRIMARY KEY,
          started_at TEXT NOT NULL,
          completed_at TEXT,
          mode TEXT NOT NULL,
          status TEXT NOT NULL,
          summary_json TEXT NOT NULL
        );
        """
    )


def _upsert_selectors(
    conn: sqlite3.Connection,
    *,
    selectors: list[dict[str, Any]],
    run_id: str,
    observed_at: str,
) -> None:
    for row in selectors:
        selector_key = str(row.get("selector_key") or "").strip()
        if not selector_key:
            continue
        existing = conn.execute(
            "SELECT first_seen_at FROM selectors WHERE selector_key = ?",
            (selector_key,),
        ).fetchone()
        first_seen = str(existing[0]) if existing else observed_at
        conn.execute(
            """
            INSERT INTO selectors (
              selector_key, kind, role, selector_id, status, repo_url, launch_env_json,
              first_seen_at, last_seen_at, source_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(selector_key) DO UPDATE SET
              kind = excluded.kind,
              role = excluded.role,
              selector_id = excluded.selector_id,
              status = excluded.status,
              repo_url = excluded.repo_url,
              launch_env_json = excluded.launch_env_json,
              last_seen_at = excluded.last_seen_at,
              source_run_id = excluded.source_run_id
            """,
            (
                selector_key,
                str(row.get("kind") or ""),
                str(row.get("role") or ""),
                str(row.get("selector_id") or ""),
                _normalize_status(row.get("status")),
                str(row.get("repo_url") or ""),
                _json_dumps(row.get("launch_env") or {}),
                first_seen,
                observed_at,
                run_id,
            ),
        )


def _insert_transitions(
    conn: sqlite3.Connection,
    *,
    changes: list[dict[str, Any]],
    run_id: str,
    observed_at: str,
) -> None:
    for change in changes:
        if not isinstance(change, dict):
            continue
        kind = str(change.get("kind") or "").strip()
        selector_id = str(change.get("selector_id") or "").strip()
        selector_key = str(change.get("key") or "").strip()
        if not selector_key:
            selector_key = f"{kind or 'unknown'}:{selector_id or 'unknown'}"
        conn.execute(
            """
            INSERT INTO selector_transitions (
              selector_key, status_from, status_to, transition_type, observed_at, run_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                selector_key,
                str(change.get("status_from") or ""),
                str(change.get("status_to") or ""),
                str(change.get("change_type") or "changed"),
                observed_at,
                run_id,
            ),
        )


def _upsert_actions(
    conn: sqlite3.Connection,
    *,
    actions: list[dict[str, Any]],
    run_id: str,
    planned_at: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        selector_key = _selector_key_for_action(action)
        selector_id = str(action.get("selector_id") or "").strip()
        role = str(action.get("role") or "").strip()
        queue_state = _queue_state_from_action(action)
        reason = ""
        missing = action.get("missing_requirements")
        missing_list = missing if isinstance(missing, list) else []
        if missing_list:
            reason = f"missing required launch env: {', '.join(str(item) for item in missing_list)}"
        elif queue_state == "failed":
            reason = f"docker compose exit code {int(action.get('returncode') or 1)}"

        queue_id = f"{run_id}:{index}:{selector_key}:{_normalize_status(action.get('status_to'))}"
        completed_at = (
            planned_at if queue_state in {"launched", "failed", "skipped"} else None
        )
        conn.execute(
            """
            INSERT INTO launch_queue (
              queue_id, selector_key, role, selector_id, trigger_status, state, reason,
              compose_project, compose_file, host_port, launch_env_json,
              planned_at, claimed_at, completed_at, run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                queue_id,
                selector_key,
                role,
                selector_id,
                _normalize_status(action.get("status_to")),
                queue_state,
                reason,
                str(action.get("project") or ""),
                str(action.get("compose_file") or ""),
                int(action.get("host_port") or 0)
                if action.get("host_port") is not None
                else None,
                _json_dumps(action.get("launch_env") or {}),
                planned_at,
                planned_at
                if queue_state in {"launching", "launched", "failed"}
                else None,
                completed_at,
                run_id,
            ),
        )

        if bool(action.get("executed")) or queue_state in {"failed", "skipped"}:
            runtime_state = _container_state_from_action(action)
            conn.execute(
                """
                INSERT INTO containers (
                  selector_key, role, selector_id, compose_project, container_name, host_port,
                  runtime_state, started_at, updated_at, last_exit_code, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(selector_key) DO UPDATE SET
                  role = excluded.role,
                  selector_id = excluded.selector_id,
                  compose_project = excluded.compose_project,
                  container_name = excluded.container_name,
                  host_port = excluded.host_port,
                  runtime_state = excluded.runtime_state,
                  started_at = COALESCE(containers.started_at, excluded.started_at),
                  updated_at = excluded.updated_at,
                  last_exit_code = excluded.last_exit_code,
                  last_error = excluded.last_error
                """,
                (
                    selector_key,
                    role,
                    selector_id,
                    str(action.get("project") or ""),
                    str(action.get("container_name") or ""),
                    int(action.get("host_port") or 0)
                    if action.get("host_port") is not None
                    else None,
                    runtime_state,
                    planned_at if runtime_state == "running" else None,
                    planned_at,
                    int(action.get("returncode") or 0)
                    if action.get("returncode") is not None
                    else None,
                    str(action.get("output") or "")[:2000],
                ),
            )
        events.append(
            {
                "selector_key": selector_key,
                "selector_id": selector_id,
                "role": role,
                "state": queue_state,
                "status_to": _normalize_status(action.get("status_to")),
            }
        )
    return events


def _query_latest_queue_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT queue_id, selector_key, role, selector_id, trigger_status, state, reason,
               compose_project, compose_file, host_port, launch_env_json,
               planned_at, claimed_at, completed_at, run_id
        FROM launch_queue
        ORDER BY planned_at DESC, queue_id DESC
        """
    ).fetchall()
    result: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for row in rows:
        selector_key = str(row[1] or "")
        if selector_key in seen_keys:
            continue
        seen_keys.add(selector_key)
        result.append(
            {
                "queue_id": row[0],
                "selector_key": selector_key,
                "role": row[2],
                "selector_id": row[3],
                "trigger_status": row[4],
                "state": row[5],
                "reason": row[6],
                "compose_project": row[7],
                "compose_file": row[8],
                "host_port": row[9],
                "launch_env": json.loads(row[10]) if row[10] else {},
                "planned_at": row[11],
                "claimed_at": row[12],
                "completed_at": row[13],
                "run_id": row[14],
            }
        )
    return result


def _query_containers(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT selector_key, role, selector_id, compose_project, container_name, host_port,
               runtime_state, started_at, updated_at, last_exit_code, last_error
        FROM containers
        ORDER BY updated_at DESC, selector_key ASC
        """
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "selector_key": row[0],
                "role": row[1],
                "selector_id": row[2],
                "compose_project": row[3],
                "container_name": row[4],
                "host_port": row[5],
                "runtime_state": row[6],
                "started_at": row[7],
                "updated_at": row[8],
                "last_exit_code": row[9],
                "last_error": row[10],
            }
        )
    return result


def _build_status_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    queue_rows = _query_latest_queue_rows(conn)
    containers = _query_containers(conn)
    buckets: dict[str, list[dict[str, Any]]] = {
        "ready": [],
        "launching": [],
        "launched": [],
        "failed": [],
        "skipped": [],
    }
    for row in queue_rows:
        state = str(row.get("state") or "unknown")
        if state in buckets:
            buckets[state].append(row)

    running = [
        row for row in containers if str(row.get("runtime_state") or "") == "running"
    ]
    return {
        "generated_at_utc": _utc_now(),
        "summary": {
            "queue_total": len(queue_rows),
            "ready_to_launch": len(buckets["ready"]),
            "launching": len(buckets["launching"]),
            "launched": len(buckets["launched"]),
            "failed": len(buckets["failed"]),
            "skipped": len(buckets["skipped"]),
            "containers_tracked": len(containers),
            "containers_running": len(running),
        },
        "ready": buckets["ready"],
        "launching": buckets["launching"],
        "launched": buckets["launched"],
        "failed": buckets["failed"],
        "skipped": buckets["skipped"],
        "containers": containers,
    }


def _post_webhook(url: str, payload: dict[str, Any]) -> None:
    if not url.strip():
        return
    req = urllib.request.Request(
        url.strip(),
        data=_json_dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):  # noqa: S310
            return
    except urllib.error.URLError:
        return


def _run_discovery(
    *,
    python_bin: str,
    discover_script: Path,
    ea_repo_url: str,
    workdir: Path,
    mode: str,
    allow_inactive: bool,
    trigger_statuses: str,
    launch_compose_root: Path,
    initiatives_catalog: str,
    engagements_catalog: str,
    domain_registry_catalog: str,
    implementation_catalog: str,
    baseline_json: Path,
) -> tuple[int, Path]:
    json_out = workdir / "enterprise-repo-graph.json"
    cmd = [
        python_bin,
        str(discover_script),
        "--ea-repo-url",
        ea_repo_url,
        "--output",
        "json",
        "--json-out",
        str(json_out),
        "--workdir",
        str(workdir),
        "--initiatives-catalog",
        initiatives_catalog,
        "--engagements-catalog",
        engagements_catalog,
        "--domain-registry-catalog",
        domain_registry_catalog,
        "--implementation-catalog",
        implementation_catalog,
        "--trigger-statuses",
        trigger_statuses,
    ]
    if allow_inactive:
        cmd.append("--allow-inactive")
    if baseline_json.exists():
        cmd.extend(["--baseline-json", str(baseline_json)])
    if mode in {"plan", "launch"}:
        cmd.append("--plan-launches")
    if mode == "launch":
        cmd.extend(
            ["--launch-containers", "--launch-compose-root", str(launch_compose_root)]
        )

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr)
    return completed.returncode, json_out


def _store_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    started_at: str,
    completed_at: str,
    mode: str,
    status: str,
    summary: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO runs (run_id, started_at, completed_at, mode, status, summary_json)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
          completed_at = excluded.completed_at,
          mode = excluded.mode,
          status = excluded.status,
          summary_json = excluded.summary_json
        """,
        (run_id, started_at, completed_at, mode, status, _json_dumps(summary)),
    )


def _process_once(args: argparse.Namespace) -> int:
    run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    started_at = _utc_now()

    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    db_path = Path(args.db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    status_json_path = Path(args.status_json).resolve()
    status_json_path.parent.mkdir(parents=True, exist_ok=True)

    discover_script = Path(args.discover_script).resolve()
    baseline_json = (
        Path(args.baseline_json).resolve()
        if args.baseline_json
        else (workdir / "enterprise-repo-graph.json")
    )

    returncode, json_report_path = _run_discovery(
        python_bin=sys.executable,
        discover_script=discover_script,
        ea_repo_url=args.ea_repo_url,
        workdir=workdir,
        mode=args.mode,
        allow_inactive=bool(args.allow_inactive),
        trigger_statuses=args.trigger_statuses,
        launch_compose_root=Path(args.launch_compose_root).resolve(),
        initiatives_catalog=args.initiatives_catalog,
        engagements_catalog=args.engagements_catalog,
        domain_registry_catalog=args.domain_registry_catalog,
        implementation_catalog=args.implementation_catalog,
        baseline_json=baseline_json,
    )

    report: dict[str, Any] = {}
    if json_report_path.exists():
        report = json.loads(json_report_path.read_text(encoding="utf-8"))
        baseline_json.write_text(
            json_report_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
    elif returncode != 0:
        report = {
            "summary": {"errors": 1},
            "validation": {
                "errors": [f"discovery failed with return code {returncode}"],
                "warnings": [],
            },
            "status_tracking": {"changes": []},
            "automation": {"planned_actions": []},
            "initiatives": [],
        }

    selectors = _extract_selectors(report)
    changes = report.get("status_tracking", {}).get("changes")
    if not isinstance(changes, list):
        changes = []
    planned_actions = report.get("automation", {}).get("planned_actions")
    if not isinstance(planned_actions, list):
        planned_actions = []

    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        _upsert_selectors(
            conn, selectors=selectors, run_id=run_id, observed_at=started_at
        )
        _insert_transitions(
            conn, changes=changes, run_id=run_id, observed_at=started_at
        )
        events = _upsert_actions(
            conn, actions=planned_actions, run_id=run_id, planned_at=started_at
        )

        status_payload = _build_status_payload(conn)
        completed_at = _utc_now()
        run_status = "success"
        if returncode != 0:
            run_status = "failed"
        elif int(report.get("summary", {}).get("errors") or 0) > 0:
            run_status = "partial"
        _store_run(
            conn,
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            mode=args.mode,
            status=run_status,
            summary=report.get("summary", {})
            if isinstance(report.get("summary"), dict)
            else {},
        )
        conn.commit()

    status_json_path.write_text(_json_dumps(status_payload) + "\n", encoding="utf-8")
    print(f"state_db={db_path}")
    print(f"status_json={status_json_path}")
    print(f"run_id={run_id}")

    webhook = str(args.notify_webhook_url or "").strip()
    if webhook and events:
        _post_webhook(
            webhook,
            {
                "run_id": run_id,
                "generated_at_utc": _utc_now(),
                "events": events,
            },
        )

    return 0 if returncode == 0 else int(returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scheduled selector launch manager: run discovery, persist launch state in SQLite, "
            "and publish web status JSON."
        )
    )
    parser.add_argument(
        "--ea-repo-url", required=True, help="EA repo URL for discovery entrypoint."
    )
    parser.add_argument(
        "--mode",
        choices=["report_only", "plan", "launch"],
        default="report_only",
        help="Execution mode.",
    )
    parser.add_argument(
        "--workdir",
        default=str(
            Path(__file__).resolve().parents[1] / ".tmp" / "enterprise-repo-graph"
        ),
        help="Working directory for discovery outputs.",
    )
    parser.add_argument(
        "--db-path",
        default=str(
            Path(__file__).resolve().parents[1]
            / ".tmp"
            / "enterprise-repo-graph"
            / "state"
            / "launch_state.db"
        ),
        help="SQLite state DB path.",
    )
    parser.add_argument(
        "--status-json",
        default=str(
            Path(__file__).resolve().parents[1]
            / "web"
            / "enterprise-repo-graph-viewer"
            / "status.json"
        ),
        help="Published runtime status JSON path for web viewer.",
    )
    parser.add_argument(
        "--baseline-json",
        default=None,
        help="Optional baseline JSON path. Defaults to <workdir>/enterprise-repo-graph.json.",
    )
    parser.add_argument(
        "--discover-script",
        default=str(
            Path(__file__).resolve().parent / "discover_enterprise_repo_graph.py"
        ),
        help="Path to discover_enterprise_repo_graph.py.",
    )
    parser.add_argument("--trigger-statuses", default="approved,ready,in_progress")
    parser.add_argument("--allow-inactive", action="store_true")
    parser.add_argument(
        "--launch-compose-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Compose root for launch mode.",
    )
    parser.add_argument(
        "--initiatives-catalog",
        default="architecture/portfolio/initiatives.yml",
    )
    parser.add_argument(
        "--engagements-catalog",
        default="architecture/solution/domain-engagements.yml",
    )
    parser.add_argument(
        "--domain-registry-catalog",
        default="architecture/enterprise/domain-registry.yml",
    )
    parser.add_argument(
        "--implementation-catalog",
        default="implementation-catalog.json",
    )
    parser.add_argument(
        "--notify-webhook-url",
        default="",
        help="Optional webhook URL for event notifications.",
    )
    parser.add_argument("--poll", action="store_true", help="Run continuously.")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=120,
        help="Polling interval when --poll is used.",
    )
    args = parser.parse_args()

    mode_map = {"report_only": "report_only", "plan": "plan", "launch": "launch"}
    args.mode = mode_map.get(args.mode, "report_only")

    if not args.poll:
        return _process_once(args)

    interval = max(10, int(args.interval_seconds or 300))
    while True:
        exit_code = _process_once(args)
        if exit_code != 0:
            print(f"manager_cycle_exit_code={exit_code}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
