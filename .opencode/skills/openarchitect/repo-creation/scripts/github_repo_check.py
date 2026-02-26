from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _read_json(url: str, token: str) -> tuple[int, dict[str, Any] | None, str | None]:
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "openarchitect-repo-creation",
        },
    )
    try:
        with urlopen(req, timeout=20) as response:  # nosec B310
            status = int(response.status)
            payload = json.loads(response.read().decode("utf-8"))
            return status, payload, None
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), None, body
    except URLError as exc:
        return 0, None, str(exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check GitHub repository existence.")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", action="append", dest="repos", required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args(argv)

    token = str(os.getenv(args.token_env) or "").strip()
    if not token:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"missing token in env var {args.token_env}",
                    "owner": args.owner,
                    "results": [],
                },
                ensure_ascii=True,
            )
        )
        return 2

    results: list[dict[str, Any]] = []
    for repo in args.repos:
        name = str(repo or "").strip()
        if not name:
            continue
        url = f"https://api.github.com/repos/{args.owner}/{name}"
        status, payload, error = _read_json(url, token)
        if status == 200 and isinstance(payload, dict):
            results.append(
                {
                    "repo": name,
                    "exists": True,
                    "private": bool(payload.get("private")),
                    "html_url": payload.get("html_url"),
                    "default_branch": payload.get("default_branch"),
                }
            )
        elif status == 404:
            results.append({"repo": name, "exists": False, "status": 404})
        else:
            results.append(
                {
                    "repo": name,
                    "exists": False,
                    "status": status,
                    "error": error,
                }
            )

    print(
        json.dumps(
            {
                "ok": True,
                "owner": args.owner,
                "results": results,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
