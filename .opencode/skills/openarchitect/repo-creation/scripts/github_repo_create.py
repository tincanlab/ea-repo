from __future__ import annotations

import argparse
import json
import os
import subprocess
from typing import Any


def _curl_json(
    *,
    url: str,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any] | None, str | None]:
    cmd = [
        "curl",
        "--silent",
        "--show-error",
        "--location",
        "--request",
        method,
        "--url",
        url,
        "--header",
        f"Authorization: Bearer {token}",
        "--header",
        "Accept: application/vnd.github+json",
        "--header",
        "User-Agent: openarchitect-repo-creation",
        "--write-out",
        "\n%{http_code}",
    ]
    if payload is not None:
        cmd.extend(
            [
                "--header",
                "Content-Type: application/json",
                "--data",
                json.dumps(payload, ensure_ascii=True),
            ]
        )

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return 0, None, "curl not found in PATH"
    except Exception as exc:
        return 0, None, str(exc)

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or "curl request failed"
        return 0, None, err

    stdout = (proc.stdout or "").rstrip("\r\n")
    if "\n" in stdout:
        body_text, status_text = stdout.rsplit("\n", 1)
    else:
        body_text, status_text = "", stdout

    try:
        status = int(status_text.strip())
    except ValueError:
        return 0, None, f"unable to parse HTTP status from curl output: {status_text}"

    payload_json: dict[str, Any] | None = None
    body_text = body_text.strip()
    if body_text:
        try:
            parsed = json.loads(body_text)
            if isinstance(parsed, dict):
                payload_json = parsed
        except json.JSONDecodeError:
            pass

    error = None if status in {200, 201} else (body_text or proc.stderr.strip() or None)
    return status, payload_json, error


def _post_json(
    url: str, token: str, payload: dict[str, Any]
) -> tuple[int, dict[str, Any] | None, str | None]:
    return _curl_json(url=url, token=token, method="POST", payload=payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create GitHub repo if missing.")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--private", action="store_true", default=True)
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    token = str(os.getenv(args.token_env) or "").strip()
    if not token:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"missing token in env var {args.token_env}",
                },
                ensure_ascii=True,
            )
        )
        return 2

    visibility_private = bool(args.private and not args.public)
    owner = str(args.owner).strip()
    repo = str(args.repo).strip()

    repo_check_url = f"https://api.github.com/repos/{owner}/{repo}"
    status, payload, error = _curl_json(url=repo_check_url, token=token)
    if status == 200 and isinstance(payload, dict):
        print(
            json.dumps(
                {
                    "ok": True,
                    "created": False,
                    "exists": True,
                    "owner": owner,
                    "repo": repo,
                    "html_url": payload.get("html_url"),
                },
                ensure_ascii=True,
            )
        )
        return 0
    if status not in {0, 404}:
        print(
            json.dumps(
                {
                    "ok": False,
                    "created": False,
                    "exists": False,
                    "owner": owner,
                    "repo": repo,
                    "status": status,
                    "error": error,
                },
                ensure_ascii=True,
            )
        )
        return 1

    if args.dry_run:
        print(
            json.dumps(
                {
                    "ok": True,
                    "created": False,
                    "exists": False,
                    "owner": owner,
                    "repo": repo,
                    "dry_run": True,
                },
                ensure_ascii=True,
            )
        )
        return 0

    user_status, user_payload, user_error = _curl_json(
        url="https://api.github.com/user",
        token=token,
    )
    if user_status != 200 or not isinstance(user_payload, dict):
        print(
            json.dumps(
                {
                    "ok": False,
                    "created": False,
                    "error": user_error or "failed to resolve authenticated user",
                },
                ensure_ascii=True,
            )
        )
        return 1
    authenticated_login = str(user_payload.get("login") or "").strip()

    endpoint = (
        "https://api.github.com/user/repos"
        if owner.lower() == authenticated_login.lower()
        else f"https://api.github.com/orgs/{owner}/repos"
    )
    create_payload = {
        "name": repo,
        "description": str(args.description or ""),
        "private": visibility_private,
    }
    create_status, created, create_error = _post_json(endpoint, token, create_payload)
    if create_status in {200, 201} and isinstance(created, dict):
        print(
            json.dumps(
                {
                    "ok": True,
                    "created": True,
                    "exists": False,
                    "owner": owner,
                    "repo": repo,
                    "html_url": created.get("html_url"),
                    "private": created.get("private"),
                },
                ensure_ascii=True,
            )
        )
        return 0

    print(
        json.dumps(
            {
                "ok": False,
                "created": False,
                "owner": owner,
                "repo": repo,
                "status": create_status,
                "error": create_error,
            },
            ensure_ascii=True,
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
