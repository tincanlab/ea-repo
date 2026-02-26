---
name: quick-start
description: Run a fast Git-first startup flow for OpenArchitect repositories, including canonical artifact validation and optional downstream repo bootstrap.
---

# Quick Start

## Overview

Use this skill to run a minimal, repeatable startup flow in a repository:
1. validate canonical structured artifacts
2. optionally bootstrap downstream repos from solution manifests

This skill is designed for first-run setup, demos, and CI smoke checks.

## Inputs

- Repository root (default: current directory)
- Optional bootstrap inputs:
  - `solution-index.yml`
  - `architecture/solution/solution-build-plan.yml`
  - target `workdir` for downstream repos

## Output

- Validation summary with warnings/errors
- Optional downstream repo bootstrap result

## Design Principles

- Git-first and deterministic: validate what is in-repo before any optional provisioning/bootstrap.
- Fast failure with remediation: every failed run should produce a concrete "what to do next" path.
- Profile-aware but explicit: document which profiles are specialized vs compatibility aliases.
- No silent governance claims: quick-start validates artifacts; architecture skills perform cascade-gated advancement.

## Profile Matrix

`run_quick_start.py` supports `--profile full|ea|sa|da|dev`.

- `ea`: specialized EA-only validation (`ENTERPRISE.md`, `ROADMAP.md`, `architecture/enterprise/*`, `architecture/portfolio/initiatives.yml`) and optional GitHub compare/sync.
- `full`: full canonical structured-artifact validation using `common/python/openarchitect_skill_common/structured_artifact_validation.py`.
- `sa`, `da`, `dev`: currently accepted for container-role compatibility; today they run the same validator path as `full` (no additional profile-specific filtering yet).

## Workflow

Set `<skills_root>` to your environment skill root:
- Codex: `.codex/skills/openarchitect`
- OpenCode: `.opencode/skills/openarchitect`

0. Preflight (required): run quick-start from a real Git repo working directory.
   - If container startup lands outside a repo, quick-start now fails fast.
   - Fix by setting `OPENARCHITECT_GIT_WORKDIR` to a cloned repo path and `cd` there.
   - Example:
```bash
export OPENARCHITECT_GIT_WORKDIR=/workspace/ea-repo
cd /workspace/ea-repo
```

1. Run quick-start validation:
```bash
python <skills_root>/quick-start/scripts/run_quick_start.py --root .
```

2. If validating a partial repo (for example only selector manifests), run:
```bash
python <skills_root>/quick-start/scripts/run_quick_start.py --root . --allow-partial --no-drift
```

3. For EA containers, validate only EA-owned artifacts:
```bash
python <skills_root>/quick-start/scripts/run_quick_start.py --root . --profile ea
```
By default, EA profile performs a read-only compare with GitHub first when repo URL is configured (`--github-repo-url` or `OPENARCHITECT_EA_REPO_URL`).
When `architecture/portfolio/initiative-pipeline.yml` exists, EA profile also checks that generated `architecture/portfolio/initiatives.yml` is in sync.

4. Optional (EA): sync key EA files from GitHub before validation:
```bash
python <skills_root>/quick-start/scripts/run_quick_start.py \
  --root . \
  --profile ea \
  --sync-from-github \
  --github-repo-url <ea_repo_url>
```

If sync fails and you need raw git diagnostics:
```bash
python <skills_root>/quick-start/scripts/run_quick_start.py \
  --root . \
  --profile ea \
  --sync-from-github \
  --github-repo-url <ea_repo_url> \
  --debug
```

To disable auto-compare in EA mode (for example offline runs):
```bash
python <skills_root>/quick-start/scripts/run_quick_start.py --root . --profile ea --no-auto-compare
```

5. Optional: bootstrap downstream repos:
```bash
python <skills_root>/quick-start/scripts/run_quick_start.py \
  --root . \
  --bootstrap \
  --solution-index solution-index.yml \
  --build-plan architecture/solution/solution-build-plan.yml \
  --workdir .work/repos \
  --no-clone
```

6. If validation fails, apply remediation by failure type:
   - Schema/YAML parse errors (`YAML parse failed`, schema validation messages):
     - Fix artifact structure using the corresponding schema/template under:
       - `<skills_root>/common/references/schemas/`
       - `docs/design/schemas/` and `docs/design/templates/` (if present in repo)
     - Re-run quick-start.
   - Drift/conformance errors (for example unknown interface IDs, missing code/spec paths, duplicate IDs):
     - Regenerate or correct source architecture artifacts with the producing skill:
       - requirements issues -> `requirement-analysis`
       - solution interface/component contract issues -> `solution-architecture`
       - domain component issues -> `domain-architecture`
     - Re-run quick-start (optionally `--no-drift` only for limited schema-only smoke checks).
   - Missing canonical artifacts in `full` profile:
     - Create missing baseline artifacts via upstream architecture skills (typically `requirement-analysis`, `solution-architecture`, `domain-architecture`) before retrying.
   - Missing EA artifacts in `ea` profile:
     - Run `enterprise-architecture` to generate EA baseline files; commit; rerun quick-start.
     - Or hydrate missing files via `--sync-from-github --profile ea --github-repo-url <ea_repo_url>`.
   - Selector drift in `ea` profile (`initiatives.yml` out of sync with `initiative-pipeline.yml`):
     - Regenerate selector:
       - `python <skills_root>/enterprise-architecture/scripts/generate_initiatives_selector.py --pipeline architecture/portfolio/initiative-pipeline.yml --out architecture/portfolio/initiatives.yml`
     - Optionally enforce in CI:
       - `python <skills_root>/enterprise-architecture/scripts/generate_initiatives_selector.py --pipeline architecture/portfolio/initiative-pipeline.yml --out architecture/portfolio/initiatives.yml --check`
   - EA GitHub sync/compare failures:
     - repo not found -> verify URL/access; create repo with `repo-creation` if needed.
     - auth failure -> set `GITHUB_TOKEN`/`GH_TOKEN`.
     - network/DNS failure -> fix connectivity and retry.
     - empty repo -> run `enterprise-architecture`, commit baseline, then retry sync.
     - use `--debug` for raw git diagnostics.

7. Exit code semantics (for CI):
   - `0`: success
   - `1`: validation failed (artifact/schema/drift problems)
   - `2`: usage/config error (unsupported mode/args, explicit fail-on-diff policy hit)
   - `3`: sync failure category (`SyncError`)
   - `99`: unexpected runtime error

## Cross-Skill Guidance

- Use `quick-start` first when re-entering a repo to determine whether you can proceed directly or must regenerate prerequisites.
- If quick-start reveals missing upstream architecture artifacts, run the upstream skill before downstream work:
  - enterprise guardrails missing -> `enterprise-architecture`
  - requirements baseline missing -> `requirement-analysis`
  - solution design/contracts missing -> `solution-architecture`
  - domain design/specs missing -> `domain-architecture`
- After remediation, rerun `quick-start` to confirm a clean baseline before `constraint-validation` and promotion discussions.
- For broad skill routing and cascade context, use `.codex/skills/openarchitect/SKILL_SELECTION.md`.

## Notes

- Validation is backed by `<skills_root>/common/python/openarchitect_skill_common/structured_artifact_validation.py`.
- Bootstrap is backed by `<skills_root>/common/python/openarchitect_skill_common/repo_bootstrap.py`.
- EA sync behavior:
  - EA validation now auto-compares local EA files against GitHub in read-only mode when repo URL is configured.
  - Missing local EA files are hydrated from GitHub.
  - If a local file differs from GitHub, quick-start prints `REVIEW_REQUIRED` and does not overwrite.
  - Use `--fail-on-sync-diff` if you want diff detection to fail the run.
  - Sync preflight reports clearer causes for repo-not-found, auth, empty-repo, and network failures.
  - If the EA repo is empty, quick-start will prompt you to run the `enterprise-architecture` skill first, commit baseline EA artifacts, then retry sync.
  - If `initiative-pipeline.yml` is present, quick-start enforces generated-selector consistency to prevent routing drift.
- This skill is Git-first and does not require a workspace DB.
