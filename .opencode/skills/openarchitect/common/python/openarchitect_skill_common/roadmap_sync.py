from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml


_KIND_RE = re.compile(r"^#\s*ROADMAP\s*\(\s*(?P<kind>[^)]+)\s*\)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Roadmap:
    kind: str  # enterprise|solution|domain
    key: str
    updated_at: str  # YYYY-MM-DD
    status: dict[str, Any]
    milestones: list[dict[str, str]]
    dependencies: list[dict[str, str]]
    sources: list[dict[str, str]]
    meta: dict[str, Any]


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strip_ticks(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        return value[1:-1].strip()
    return value


def _infer_kind(markdown: str) -> str | None:
    for line in markdown.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _KIND_RE.match(line)
        if not match:
            return None
        raw = match.group("kind").strip().lower()
        if raw.startswith("enter"):
            return "enterprise"
        if raw.startswith("sol"):
            return "solution"
        if raw.startswith("dom"):
            return "domain"
        return None
    return None


def _extract_first_bullet_value(markdown: str, label: str) -> str | None:
    # Matches: "- Label: value"
    pattern = re.compile(rf"(?m)^\-\s+{re.escape(label)}\s*:\s*(?P<value>.+?)\s*$")
    match = pattern.search(markdown)
    if not match:
        return None
    return _strip_ticks(match.group("value"))


def _extract_risk_list(markdown: str, header: str) -> list[str]:
    # In "## Current Status" block, expect:
    # - <header>:
    #   - risk
    #   - risk
    lines = markdown.splitlines()
    in_status = False
    capturing = False
    risks: list[str] = []
    for line in lines:
        if line.startswith("## "):
            in_status = line.strip().lower() == "## current status"
            capturing = False
            continue
        if not in_status:
            continue
        if re.match(rf"^\-\s+{re.escape(header)}\s*:\s*$", line.strip(), flags=re.IGNORECASE):
            capturing = True
            continue
        if capturing:
            if line.startswith("- "):
                # next top-level bullet ends the list
                break
            m = re.match(r"^\s+\-\s+(?P<risk>.+?)\s*$", line)
            if m:
                risks.append(_strip_ticks(m.group("risk")))
    return [r for r in (risk.strip() for risk in risks) if r]


def _extract_list_items_under_heading(markdown: str, heading: str) -> list[str]:
    # heading like "### Milestones" or "### Domain Roll-Up (Links)"
    lines = markdown.splitlines()
    in_block = False
    items: list[str] = []
    for line in lines:
        if line.startswith("### "):
            in_block = line.strip().lower() == f"### {heading}".lower()
            continue
        if in_block:
            if line.startswith("## "):
                break
            if line.startswith("### "):
                break
            m = re.match(r"^\-\s+(?P<item>.+?)\s*$", line)
            if m:
                items.append(m.group("item").strip())
    return items


def _parse_milestone(item: str) -> dict[str, str] | None:
    # "<id>: <target>: <goal>"
    parts = [part.strip() for part in item.split(":", 2)]
    if len(parts) != 3:
        return None
    milestone_id, target, goal = parts
    if not milestone_id or not target or not goal:
        return None
    return {"id": milestone_id, "target": target, "goal": goal}


def _parse_dependency(item: str) -> dict[str, str] | None:
    # "<from> depends on <to>: <note>: <target>"
    if " depends on " not in item:
        return None
    left, rest = item.split(" depends on ", 1)
    from_part = left.strip()
    to_part, sep, note_target = rest.partition(":")
    if not sep:
        return None
    to_part = to_part.strip()
    note_target = note_target.strip()
    if ":" not in note_target:
        return None
    note, target = [part.strip() for part in note_target.rsplit(":", 1)]
    if not from_part or not to_part or not target:
        return None
    return {"from": from_part, "to": to_part, "note": note, "target": target}


def _parse_github_blob_ref(value: str) -> dict[str, str] | None:
    # "<name>: <repo-url>/blob/<ref>/<path>"
    if ": " not in value:
        return None
    name, url = value.split(": ", 1)
    name = name.strip()
    url = url.strip()
    if "/blob/" not in url:
        return None
    repo_url, remainder = url.split("/blob/", 1)
    if "/" not in remainder:
        return None
    commitish, path = remainder.split("/", 1)
    path = path.strip()
    if not name or not repo_url or not commitish or not path:
        return None
    return {"name": name, "repo_url": repo_url, "path": path, "commit": commitish}


def generate_roadmap_yaml(
    *,
    markdown_text: str,
    markdown_path: str = "ROADMAP.md",
    markdown_sha256: str,
    kind: str | None = None,
    today: date | None = None,
) -> Roadmap:
    inferred = _infer_kind(markdown_text)
    roadmap_kind = (kind or inferred or "").strip().lower()
    if roadmap_kind not in {"enterprise", "solution", "domain"}:
        raise ValueError("Unable to infer roadmap kind. Use '# ROADMAP (Solution|Domain|Enterprise)' or pass --kind.")

    key_label = {
        "enterprise": "Enterprise key",
        "solution": "Solution key",
        "domain": "Domain key",
    }[roadmap_kind]
    roadmap_key = _extract_first_bullet_value(markdown_text, key_label)
    if not roadmap_key or roadmap_key.startswith("<"):
        raise ValueError(f"Missing `{key_label}` in ROADMAP.md Scope section.")

    status_health = _extract_first_bullet_value(markdown_text, "Health")
    if not status_health:
        raise ValueError("Missing `- Health: ...` in ROADMAP.md Current Status section.")
    status_health = status_health.strip().lower()
    if status_health not in {"green", "yellow", "red"}:
        raise ValueError("Health must be one of: green, yellow, red.")

    current = _extract_first_bullet_value(markdown_text, "Current milestone") or _extract_first_bullet_value(
        markdown_text, "Current theme"
    )
    next_value = _extract_first_bullet_value(markdown_text, "Next milestone") or _extract_first_bullet_value(
        markdown_text, "Next theme"
    )

    risks_header = {
        "enterprise": "Top enterprise risks",
        "solution": "Key cross-domain risks",
        "domain": "Key risks",
    }[roadmap_kind]
    risks = _extract_risk_list(markdown_text, risks_header)

    milestone_items = _extract_list_items_under_heading(markdown_text, "Milestones")
    milestones: list[dict[str, str]] = []
    for item in milestone_items:
        parsed = _parse_milestone(item)
        if parsed:
            milestones.append(parsed)

    dep_heading = "Cross-Solution Dependencies" if roadmap_kind == "enterprise" else "Cross-Domain Dependencies"
    dep_items = _extract_list_items_under_heading(markdown_text, dep_heading)
    dependencies: list[dict[str, str]] = []
    for item in dep_items:
        parsed = _parse_dependency(item)
        if parsed:
            dependencies.append(parsed)

    source_heading = "Solution Roll-Up (Links)" if roadmap_kind == "enterprise" else "Domain Roll-Up (Links)"
    source_items = _extract_list_items_under_heading(markdown_text, source_heading)
    sources: list[dict[str, str]] = []
    for item in source_items:
        parsed = _parse_github_blob_ref(item)
        if parsed:
            sources.append(parsed)

    if today is None:
        today = date.today()
    updated_at = today.isoformat()

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    meta = {
        "generated_from": {
            "path": markdown_path,
            "sha256": markdown_sha256,
            "generated_at": generated_at,
        }
    }

    status: dict[str, Any] = {"health": status_health}
    if current:
        status["current"] = current
    if next_value:
        status["next"] = next_value
    if risks:
        status["risks"] = risks

    return Roadmap(
        kind=roadmap_kind,
        key=roadmap_key,
        updated_at=updated_at,
        status=status,
        milestones=milestones,
        dependencies=dependencies,
        sources=sources,
        meta=meta,
    )


def sync_roadmap(md_path: Path, yml_path: Path, kind: str | None = None, check: bool = False) -> int:
    md_bytes = md_path.read_bytes()
    md_text = md_bytes.decode("utf-8")
    md_hash = _sha256_hex(md_bytes)

    roadmap = generate_roadmap_yaml(
        markdown_text=md_text,
        markdown_path=str(md_path.name),
        markdown_sha256=md_hash,
        kind=kind,
    )

    payload: dict[str, Any] = {
        "kind": roadmap.kind,
        "key": roadmap.key,
        "updated_at": roadmap.updated_at,
        "status": roadmap.status,
        "milestones": roadmap.milestones,
        "dependencies": roadmap.dependencies,
        "sources": roadmap.sources,
        "meta": roadmap.meta,
    }

    # Keep output stable for diffs.
    yml_text = yaml.safe_dump(payload, sort_keys=False)

    if check:
        if not yml_path.exists():
            raise SystemExit(f"{yml_path} missing (run without --check to generate).")
        try:
            existing_payload = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit(f"{yml_path} unreadable YAML: {exc}")

        try:
            existing_hash = (
                existing_payload.get("meta", {})
                .get("generated_from", {})
                .get("sha256", "")
            )
        except AttributeError:
            existing_hash = ""

        if existing_hash != md_hash:
            raise SystemExit(f"{yml_path} out of date (ROADMAP.md hash mismatch).")

        # Lightweight sanity: kind/key should still line up with the current markdown.
        if str(existing_payload.get("kind", "")).strip().lower() != roadmap.kind:
            raise SystemExit(f"{yml_path} kind mismatch (expected {roadmap.kind}).")
        if str(existing_payload.get("key", "")).strip() != roadmap.key:
            raise SystemExit(f"{yml_path} key mismatch (expected {roadmap.key}).")

        return 0

    if yml_path.exists():
        # Avoid noisy diffs: if the source hash matches, don't rewrite the file.
        try:
            existing_payload = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
            existing_hash = (
                existing_payload.get("meta", {})
                .get("generated_from", {})
                .get("sha256", "")
            )
            if existing_hash == md_hash:
                return 0
        except Exception:
            # If the existing file is unreadable, overwrite it with a clean version.
            pass

    yml_path.write_text(yml_text, encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ROADMAP.yml from ROADMAP.md (humans edit MD; tools use YAML).")
    parser.add_argument("--md", type=Path, default=Path("ROADMAP.md"), help="Path to ROADMAP.md")
    parser.add_argument("--yml", type=Path, default=Path("ROADMAP.yml"), help="Path to ROADMAP.yml")
    parser.add_argument("--kind", choices=["enterprise", "solution", "domain"], help="Override inferred kind")
    parser.add_argument("--check", action="store_true", help="Fail if ROADMAP.yml is missing or out of date")
    args = parser.parse_args()
    return sync_roadmap(args.md, args.yml, kind=args.kind, check=args.check)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
