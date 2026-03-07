from __future__ import annotations

import argparse
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


# Canonical distributed skill content is owned by worker_container.
SOURCE_REL = Path(".opencode/skills/openarchitect")
BUNDLE_ROOT = Path(".codex/skills/openarchitect")
SKIP_DIR_NAMES = {"__pycache__", "_planned"}
SKIP_FILE_NAMES = {".DS_Store"}
TEMPLATE_PROMOTION_MAP = (
    (
        Path("../enterprise.md/templates/AGENTS.ea.md.template"),
        Path(
            ".opencode/skills/openarchitect/enterprise-architecture/references/AGENTS.ea.md.template"
        ),
    ),
    (
        Path("../enterprise.md/templates/AGENTS.sa.md.template"),
        Path(
            ".opencode/skills/openarchitect/solution-architecture/references/AGENTS.sa.md.template"
        ),
    ),
    (
        Path("../enterprise.md/templates/AGENTS.da.md.template"),
        Path(
            ".opencode/skills/openarchitect/domain-architecture/references/AGENTS.da.md.template"
        ),
    ),
    (
        Path("../enterprise.md/templates/AGENTS.dev.md.template"),
        Path(".opencode/skills/openarchitect/common/references/AGENTS.dev.md.template"),
    ),
    (
        Path("../enterprise.md/templates/ENTERPRISE.md.template"),
        Path(
            ".opencode/skills/openarchitect/enterprise-architecture/references/ENTERPRISE.md.template"
        ),
    ),
    (
        Path("../enterprise.md/templates/SOLUTION.md.template"),
        Path(
            ".opencode/skills/openarchitect/solution-architecture/references/SOLUTION.md.template"
        ),
    ),
    (
        Path("../enterprise.md/templates/DOMAIN.md.template"),
        Path(".opencode/skills/openarchitect/domain-architecture/references/DOMAIN.md.template"),
    ),
    (
        Path("../enterprise.md/templates/solution-index.yml.template"),
        Path(
            ".opencode/skills/openarchitect/solution-architecture/references/solution-index.yml.template"
        ),
    ),
    (
        Path("../enterprise.md/templates/domain-workstreams.yml.template"),
        Path(
            ".opencode/skills/openarchitect/solution-architecture/references/domain-workstreams.yml.template"
        ),
    ),
    (
        Path("../enterprise.md/templates/initiative-pipeline.yml.template"),
        Path(
            ".opencode/skills/openarchitect/enterprise-architecture/references/initiative-pipeline.yml.template"
        ),
    ),
    (
        Path("../enterprise.md/templates/initiatives.yml.template"),
        Path(
            ".opencode/skills/openarchitect/enterprise-architecture/references/initiatives.yml.template"
        ),
    ),
    (
        Path("../enterprise.md/templates/domain-registry.yml.template"),
        Path(
            ".opencode/skills/openarchitect/enterprise-architecture/references/domain-registry.yml.template"
        ),
    ),
)

SCHEMA_SOURCE_DIR = Path(".opencode/skills/openarchitect/common/references/schemas")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git_short_sha(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "nogit"
    sha = completed.stdout.strip()
    return sha or "nogit"


def _iter_source_files(source_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.name in SKIP_FILE_NAMES:
            continue
        files.append(path)
    return files


def _default_output(repo_root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sha = _git_short_sha(repo_root)
    filename = f"openarchitect-skills-codex-{timestamp}-{sha}.zip"
    return repo_root / "dist" / filename


def _promote_templates(repo_root: Path, *, dry_run: bool) -> None:
    updated = 0
    for src_rel, dst_rel in TEMPLATE_PROMOTION_MAP:
        src = (repo_root / src_rel).resolve()
        dst = (repo_root / dst_rel).resolve()

        if not src.exists():
            raise FileNotFoundError(f"template source not found: {src}")
        if not src.is_file():
            raise FileNotFoundError(f"template source is not a file: {src}")

        src_text = src.read_text(encoding="utf-8")
        dst_text = dst.read_text(encoding="utf-8") if dst.exists() else None
        if dst_text == src_text:
            continue

        updated += 1
        if dry_run:
            print(f"template_update_planned={dst_rel.as_posix()} from={src_rel.as_posix()}")
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        print(f"template_updated={dst_rel.as_posix()} from={src_rel.as_posix()}")

    print(f"templates_updated={updated}")


def _check_schema_source(repo_root: Path) -> None:
    src_dir = (repo_root / SCHEMA_SOURCE_DIR).resolve()
    if not src_dir.exists():
        raise FileNotFoundError(f"schema source directory not found: {src_dir}")
    if not src_dir.is_dir():
        raise NotADirectoryError(f"schema source path is not a directory: {src_dir}")
    print(f"schema_source={src_dir}")


def build_bundle(*, output: Path, dry_run: bool) -> int:
    repo_root = _repo_root()
    source_root = (repo_root / SOURCE_REL).resolve()
    _promote_templates(repo_root, dry_run=dry_run)
    _check_schema_source(repo_root)

    if not source_root.exists():
        raise FileNotFoundError(f"source directory not found: {source_root}")
    if not source_root.is_dir():
        raise NotADirectoryError(f"source path is not a directory: {source_root}")

    files = _iter_source_files(source_root)
    if not files:
        raise RuntimeError(f"no files found under source directory: {source_root}")

    output_abs = output if output.is_absolute() else (repo_root / output)
    output_abs = output_abs.resolve()

    print(f"source={source_root}")
    print(f"files={len(files)}")
    print(f"output={output_abs}")

    if dry_run:
        return 0

    output_abs.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_abs, mode="w", compression=ZIP_DEFLATED) as bundle:
        for file_path in files:
            rel_to_source = file_path.relative_to(source_root)
            arcname = (BUNDLE_ROOT / rel_to_source).as_posix()
            bundle.write(file_path, arcname=arcname)

    print("bundle_created=true")
    return 0


def main() -> int:
    repo_root = _repo_root()
    parser = argparse.ArgumentParser(
        description=(
            "Build a portable skills bundle that includes only "
            ".opencode/skills/openarchitect/** "
            "packaged as .codex/skills/openarchitect/**"
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_output(repo_root),
        help="Output .zip path (default: dist/openarchitect-skills-codex-<timestamp>-<sha>.zip).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be bundled without creating an archive.",
    )
    args = parser.parse_args()

    return build_bundle(
        output=args.output,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())


