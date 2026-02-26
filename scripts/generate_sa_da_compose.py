#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SA_OUT = ROOT / "docker-compose.sa.yml"
DA_OUT = ROOT / "docker-compose.da.yml"
DEFAULT_GITHUB_HOST = "github.com"


def prompt_required(label: str, default: str | None = None) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        try:
            value = input(f"{label}{suffix}: ").strip()
        except EOFError:
            raise KeyboardInterrupt
        if not value and default:
            return default
        if value:
            return value
        print("Value is required.")


def prompt_yes_no(label: str, default_yes: bool = False) -> bool:
    default_marker = "Y/n" if default_yes else "y/N"
    try:
        value = input(f"{label} ({default_marker}): ").strip().lower()
    except EOFError:
        raise KeyboardInterrupt
    if not value:
        return default_yes
    return value in {"y", "yes"}


def normalize_github_url(raw: str, *, github_host: str) -> str:
    value = raw.strip()
    if "<" in value or ">" in value or "__REQUIRED_" in value:
        raise ValueError("Placeholder value detected. Set a real GitHub repo URL.")
    if value.endswith(".git"):
        value = value[:-4]
    expected_prefix = f"https://{github_host}/"
    if re.match(rf"^https://{re.escape(github_host)}/[^/]+/[^/]+$", value):
        return value
    raise ValueError(f"Expected repo URL format: {expected_prefix}<org>/<repo>")


def normalize_github_host(raw: str) -> str:
    value = raw.strip().lower()
    if not value:
        raise ValueError("GitHub host cannot be empty.")
    if "<" in value or ">" in value or "__REQUIRED_" in value:
        raise ValueError("Placeholder value detected. Set a real GitHub host.")
    if not re.match(r"^[a-z0-9.-]+$", value):
        raise ValueError("GitHub host contains invalid characters.")
    return value


def validate_id(value: str, *, label: str, required_prefix: str | None = None) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} is required.")
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", normalized):
        raise ValueError(f"{label} must match ^[a-z0-9][a-z0-9-]*$.")
    if required_prefix and not normalized.startswith(required_prefix):
        raise ValueError(f"{label} must start with '{required_prefix}'.")
    return normalized


def prompt_validated(
    label: str,
    *,
    default: str | None = None,
    validator,
):
    while True:
        raw = prompt_required(label, default)
        try:
            return validator(raw)
        except ValueError as exc:
            print(f"Invalid value: {exc}")


def write_file(path: Path, content: str) -> None:
    if path.exists() and not prompt_yes_no(f"{path.name} exists. Overwrite?", default_yes=False):
        print(f"Skipped: {path.name}")
        return
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Wrote: {path.name}")


def build_sa_compose(initiative_id: str, ea_repo_url: str, selector_catalog: str) -> str:
    return (
        "services:\n"
        "  opencode:\n"
        "    environment:\n"
        "      OPENARCHITECT_CONTAINER_ROLE: sa\n"
        f"      INITIATIVE_ID: {initiative_id}\n"
        f"      OPENARCHITECT_EA_REPO_URL: {ea_repo_url}\n"
        f"      OPENARCHITECT_SELECTOR_CATALOG: {selector_catalog}\n"
        "      OPENARCHITECT_GIT_WORKDIR: /home/op/project\n"
    )


def build_da_compose(engagement_id: str, sa_repo_url: str) -> str:
    return (
        "services:\n"
        "  opencode:\n"
        "    environment:\n"
        "      OPENARCHITECT_CONTAINER_ROLE: da\n"
        f"      ENGAGEMENT_ID: {engagement_id}\n"
        f"      OPENARCHITECT_SA_REPO_URL: {sa_repo_url}\n"
        "      OPENARCHITECT_GIT_WORKDIR: /home/op/project\n"
    )


def main() -> int:
    print("Generate docker compose files for SA and DA roles")
    print(f"Output directory: {ROOT}")
    print("")

    github_host = prompt_validated(
        "GitHub host",
        default=DEFAULT_GITHUB_HOST,
        validator=normalize_github_host,
    )

    initiative_id = prompt_validated(
        "SA INITIATIVE_ID",
        default="init-bss-modernization",
        validator=lambda raw: validate_id(
            raw, label="INITIATIVE_ID", required_prefix="init-"
        ),
    )

    ea_repo_url = prompt_validated(
        f"SA OPENARCHITECT_EA_REPO_URL (for example https://{github_host}/acme/ea-repo)",
        validator=lambda raw: normalize_github_url(raw, github_host=github_host),
    )

    selector_catalog = prompt_required(
        "SA OPENARCHITECT_SELECTOR_CATALOG",
        "architecture/portfolio/initiatives.yml",
    )

    engagement_default = f"eng-{initiative_id}-om"
    engagement_id = prompt_validated(
        "DA ENGAGEMENT_ID",
        default=engagement_default,
        validator=lambda raw: validate_id(
            raw, label="ENGAGEMENT_ID", required_prefix="eng-"
        ),
    )

    sa_repo_url = prompt_validated(
        f"DA OPENARCHITECT_SA_REPO_URL (for example https://{github_host}/acme/solution-bss-modernization)",
        validator=lambda raw: normalize_github_url(raw, github_host=github_host),
    )

    print("")
    print("Summary")
    print(f"  GitHub host:      {github_host}")
    print(f"  SA INITIATIVE_ID: {initiative_id}")
    print(f"  SA EA repo URL:   {ea_repo_url}")
    print(f"  DA ENGAGEMENT_ID: {engagement_id}")
    print(f"  DA SA repo URL:   {sa_repo_url}")
    print("")

    if not prompt_yes_no("Write docker-compose.sa.yml and docker-compose.da.yml?", default_yes=True):
        print("Cancelled.")
        return 1

    write_file(SA_OUT, build_sa_compose(initiative_id, ea_repo_url, selector_catalog))
    write_file(DA_OUT, build_da_compose(engagement_id, sa_repo_url))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("")
        print("Cancelled.")
        raise SystemExit(130)
