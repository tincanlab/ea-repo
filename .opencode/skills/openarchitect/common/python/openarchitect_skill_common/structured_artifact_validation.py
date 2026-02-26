from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class CanonicalArtifact:
    name: str
    path: str
    schema_path: str
    required: bool = True
    glob: bool = False


CANONICAL_ARTIFACTS: tuple[CanonicalArtifact, ...] = (
    CanonicalArtifact(
        name="solution_index",
        path="solution-index.yml",
        schema_path="solution-index.schema.json",
    ),
    CanonicalArtifact(
        name="roadmap",
        path="ROADMAP.yml",
        schema_path="roadmap.schema.json",
        required=False,
    ),
    CanonicalArtifact(
        name="solution_build_plan",
        path="architecture/solution/solution-build-plan.yml",
        schema_path="solution-build-plan.schema.json",
        required=False,
    ),
    CanonicalArtifact(
        name="repo_creation_request",
        path="architecture/solution/repo-creation-request.yml",
        schema_path="repo-creation-request.schema.json",
        required=False,
    ),
    CanonicalArtifact(
        name="repo_creation_result",
        path="architecture/solution/repo-creation-result.yml",
        schema_path="repo-creation-result.schema.json",
        required=False,
    ),
    CanonicalArtifact(
        name="requirements",
        path="architecture/requirements/requirements.yml",
        schema_path="requirements.schema.json",
    ),
    CanonicalArtifact(
        name="domain_requirements",
        path="architecture/domains/*/requirements.yml",
        schema_path="domain-requirements.schema.json",
        required=False,
        glob=True,
    ),
    CanonicalArtifact(
        name="interface_contracts",
        path="architecture/solution/interface-contracts.yml",
        schema_path="interface-contracts.schema.json",
    ),
    CanonicalArtifact(
        name="component_specs",
        path="architecture/domains/*/component-specs.yml",
        schema_path="component-specs.schema.json",
        glob=True,
    ),
    CanonicalArtifact(
        name="traceability_map",
        path=".openarchitect/traceability-map.yml",
        schema_path="traceability-map.schema.json",
    ),
    CanonicalArtifact(
        name="cascade_state",
        path=".openarchitect/cascade-state.yml",
        schema_path="cascade-state.schema.json",
    ),
    CanonicalArtifact(
        name="app_topology",
        path="architecture/app_topology/app_topology.yml",
        schema_path="app-topology.schema.json",
        required=False,
    ),
    CanonicalArtifact(
        name="initiatives",
        path="architecture/portfolio/initiatives.yml",
        schema_path="initiatives.schema.json",
        required=False,
    ),
    CanonicalArtifact(
        name="initiative_pipeline",
        path="architecture/portfolio/initiative-pipeline.yml",
        schema_path="initiative-pipeline.schema.json",
        required=False,
    ),
    CanonicalArtifact(
        name="domain_engagements",
        path="architecture/solution/domain-engagements.yml",
        schema_path="domain-engagements.schema.json",
        required=False,
    ),
)


@dataclass
class ValidationResult:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _load_schema(root: Path, schema_path: str) -> dict[str, Any]:
    # Prefer bundled skill schemas so quick-start works in skills-only containers.
    bundled_schema_root = Path(__file__).resolve().parents[2] / "references" / "schemas"
    candidates: list[Path] = [
        bundled_schema_root / schema_path,
        root / "docs" / "design" / "schemas" / schema_path,
        root / schema_path,
    ]
    try:
        here = Path(__file__).resolve()
        for parent in here.parents:
            if (parent / "docs" / "design" / "schemas").exists():
                candidates.append(parent / "docs" / "design" / "schemas" / schema_path)
                break
    except Exception:  # pragma: no cover - best-effort fallback
        pass

    for candidate in candidates:
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as handle:
                return json.load(handle)

    raise FileNotFoundError(f"Schema not found: {schema_path}")


def _discover_artifacts(root: Path) -> dict[str, list[Path]]:
    discovered: dict[str, list[Path]] = {}
    for artifact in CANONICAL_ARTIFACTS:
        if artifact.glob:
            discovered[artifact.name] = sorted(root.glob(artifact.path))
        else:
            path = root / artifact.path
            discovered[artifact.name] = [path] if path.exists() else []
    return discovered


def _validate_artifact_schema(
    root: Path,
    file_path: Path,
    schema_path: str,
    errors: list[str],
) -> Any:
    try:
        payload = _load_yaml(file_path)
    except Exception as exc:  # pragma: no cover - defensive branch
        errors.append(f"{file_path}: YAML parse failed: {exc}")
        return None

    if payload is None:
        errors.append(f"{file_path}: empty YAML document is not allowed.")
        return None

    schema = _load_schema(root, schema_path)
    validator = Draft202012Validator(schema)
    validation_errors = sorted(validator.iter_errors(payload), key=lambda item: item.path)
    for item in validation_errors:
        location = ".".join(str(token) for token in item.absolute_path)
        if location:
            errors.append(f"{file_path}:{location}: {item.message}")
        else:
            errors.append(f"{file_path}: {item.message}")
    return payload


def _check_duplicate_ids(
    container: list[dict[str, Any]],
    field: str,
    file_path: Path,
    errors: list[str],
) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    collected: list[str] = []
    for row in container:
        value = str(row.get(field, "")).strip()
        if not value:
            continue
        collected.append(value)
        if value in seen:
            duplicates.append(value)
        seen.add(value)
    if duplicates:
        errors.append(f"{file_path}: duplicate {field} values: {sorted(set(duplicates))}")
    return collected


def _path_exists(root: Path, relative_path: str) -> bool:
    if "*" in relative_path or "?" in relative_path:
        return any(root.glob(relative_path))
    return (root / relative_path).exists()


def _run_drift_checks(
    root: Path,
    payloads: dict[str, list[tuple[Path, Any]]],
    errors: list[str],
) -> None:
    requirement_ids: set[str] = set()
    component_ids: set[str] = set()
    interface_ids: set[str] = set()

    for file_path, payload in payloads.get("requirements", []):
        requirement_ids.update(_check_duplicate_ids(payload["requirements"], "id", file_path, errors))

    for file_path, payload in payloads.get("component_specs", []):
        component_rows = payload["components"]
        current_ids = _check_duplicate_ids(component_rows, "id", file_path, errors)
        component_ids.update(current_ids)

        for component in component_rows:
            for code_path in component.get("code_paths", []):
                if not _path_exists(root, str(code_path)):
                    errors.append(f"{file_path}: missing code path `{code_path}`")

    interface_owner_ids: dict[str, str] = {}
    for file_path, payload in payloads.get("interface_contracts", []):
        interface_rows = payload["interfaces"]
        current_ids = _check_duplicate_ids(interface_rows, "id", file_path, errors)
        interface_ids.update(current_ids)

        for interface in interface_rows:
            spec_path = str(interface.get("spec_path", "")).strip()
            if spec_path and not _path_exists(root, spec_path):
                errors.append(f"{file_path}: missing spec path `{spec_path}`")
            interface_owner_ids[str(interface["id"])] = str(interface["owner_component_id"])

    for file_path, payload in payloads.get("component_specs", []):
        for component in payload["components"]:
            for interface_id in component.get("interfaces", []):
                if interface_ids and interface_id not in interface_ids:
                    errors.append(
                        f"{file_path}: component `{component['id']}` references unknown interface `{interface_id}`"
                    )

    for interface_id, owner_id in interface_owner_ids.items():
        if component_ids and owner_id not in component_ids:
            errors.append(
                f"interface `{interface_id}` references unknown owner_component_id `{owner_id}`"
            )

    for file_path, payload in payloads.get("traceability_map", []):
        components = payload.get("components", {})
        for component_id, mapping in components.items():
            if component_ids and component_id not in component_ids:
                errors.append(
                    f"{file_path}: traceability component `{component_id}` not found in component-specs"
                )

            for design_path in mapping.get("design_paths", []):
                if not _path_exists(root, str(design_path)):
                    errors.append(f"{file_path}: missing design path `{design_path}`")
            for code_path in mapping.get("code_paths", []):
                if not _path_exists(root, str(code_path)):
                    errors.append(f"{file_path}: missing code path `{code_path}`")
            for interface_id in mapping.get("interface_ids", []):
                if interface_ids and interface_id not in interface_ids:
                    errors.append(
                        f"{file_path}: traceability component `{component_id}` references unknown interface `{interface_id}`"
                    )

    if not requirement_ids:
        errors.append("No requirement IDs were found in canonical requirements artifact.")


def validate_structured_artifacts(
    root: Path,
    require_minimum: bool = True,
    check_drift: bool = True,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    discovered = _discover_artifacts(root)
    payloads: dict[str, list[tuple[Path, Any]]] = {artifact.name: [] for artifact in CANONICAL_ARTIFACTS}

    for artifact in CANONICAL_ARTIFACTS:
        files = discovered[artifact.name]
        if require_minimum and artifact.required and not files:
            if artifact.glob:
                errors.append(
                    f"Missing canonical artifact(s): expected at least one match for `{artifact.path}`"
                )
            else:
                errors.append(f"Missing canonical artifact: `{artifact.path}`")
            continue
        if not files:
            warnings.append(f"Optional artifact not present: `{artifact.path}`")
            continue

        for file_path in files:
            payload = _validate_artifact_schema(root, file_path, artifact.schema_path, errors)
            if payload is not None:
                payloads[artifact.name].append((file_path, payload))

    if check_drift:
        _run_drift_checks(root, payloads, errors)

    return ValidationResult(errors=errors, warnings=warnings)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate OpenArchitect canonical structured artifacts and drift checks."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to validate (default: current working directory).",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow missing canonical files; validate only discovered artifacts.",
    )
    parser.add_argument(
        "--no-drift",
        action="store_true",
        help="Run schema-only checks, skip cross-artifact drift checks.",
    )
    args = parser.parse_args()

    result = validate_structured_artifacts(
        root=Path(args.root).resolve(),
        require_minimum=not args.allow_partial,
        check_drift=not args.no_drift,
    )

    for warning in result.warnings:
        print(f"WARNING: {warning}")
    for error in result.errors:
        print(f"ERROR: {error}")

    if result.ok:
        print("Structured artifact validation passed.")
        return 0

    print(f"Structured artifact validation failed with {len(result.errors)} error(s).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
