---
name: project-intake
description: Capture and normalize project/initiative intake into the EA portfolio source artifact `architecture/portfolio/initiative-pipeline.yml`, then generate selector-ready routing data for downstream SA work.
---

# Project Intake

## Overview

Capture new initiative intake and maintain the portfolio source artifact used by EA routing.
This skill is focused on **intake quality and portfolio lifecycle state**, not architecture design.

## Repository Convention

- Source artifact (authoritative):
  - `architecture/portfolio/initiative-pipeline.yml`
- Generated routing artifact (derived):
  - `architecture/portfolio/initiatives.yml`
- Generator script:
  - `../enterprise-architecture/scripts/generate_initiatives_selector.py`

## Inputs

- Business/project intake details (minimum):
  - `initiative_id`
  - `name`
  - `stage`
  - `description`
  - `objectives` (at least one)
  - owners (`pm_owner`, `it_owner`)
- Optional routing details:
  - `solution_repo_url`
  - `routing.publish_to_selector`
  - `routing.selector_status`
- Optional business metadata:
  - `business_case_id`, `business_sponsor`, `t_shirt_size`, `roi_band`, `metadata.*`

## Outputs

- Updated `architecture/portfolio/initiative-pipeline.yml`
- Updated `architecture/portfolio/initiatives.yml` (generated)
- Commit/push reminder after successful generation (default)
- Optional auto git push when explicitly enabled

## Workflow

1. Ensure `architecture/portfolio/initiative-pipeline.yml` exists.
   - If missing, initialize it from:
     - `../enterprise-architecture/references/initiative-pipeline.yml.template`
2. Add or update intake item in pipeline by `initiative_id`.
   - Use `scripts/upsert_initiative_pipeline.py` for deterministic field updates.
3. Generate selector artifact:
   - `python ../enterprise-architecture/scripts/generate_initiatives_selector.py --pipeline architecture/portfolio/initiative-pipeline.yml --out architecture/portfolio/initiatives.yml`
4. Validate expected routing behavior:
   - If `routing.publish_to_selector=true`, initiative should appear in `initiatives.yml`.
   - If false, initiative should remain only in pipeline.

5. Approved initiative flow (required):
   - When an initiative reaches delivery approval stage (for example `approved_for_delivery`):
     - Do not publish until a real `solution_repo_url` exists.
     - Trigger handoff to `repo-creation` when repo URL is missing.
     - After repo creation succeeds, write `solution_repo_url` back to the pipeline row.
     - Then set `routing.publish_to_selector=true` and regenerate `initiatives.yml`.
   - If approval is reached but repo is not ready:
     - Keep `routing.publish_to_selector=false`.
     - Explicitly report: "approved in pipeline, pending repo creation before publication."

6. Report outcome in user-facing terms (required):
   - Always state that the initiative was added/updated in `initiative-pipeline.yml`.
   - Always state publish state for `initiatives.yml`:
     - Published when `routing.publish_to_selector=true`
     - Not yet published when `routing.publish_to_selector=false`
   - Use explicit wording:
     - "`<initiative_id>` was added to `initiative-pipeline.yml`, but not yet published to `initiatives.yml`."

7. Missing `solution_repo_url` guide (required):
   - If selector generation returns:
     - `publish_to_selector=true requires solution_repo_url`
   - Then report:
     - Initiative is in pipeline, not yet published.
     - Publication is blocked by missing repo URL.
   - Next actions:
     - Run `repo-creation` (or map an existing solution repo).
   - Update pipeline row with `solution_repo_url`.
   - Regenerate `initiatives.yml`.

8. Git follow-up (required):
   - After successful update/generation, remind user to commit and push both files.
   - If user opts in, allow automatic push:
     - `--auto-git-push`
     - optional `--git-commit-message "..."`
   - Auto-push must remain opt-in; default behavior is reminder only.

## Rules

- `initiative-pipeline.yml` is portfolio source of truth and may contain non-routable/historical items.
- `initiatives.yml` is runtime routing projection only.
- Do not manually edit `initiatives.yml` except incident recovery.
- Keep `initiative_id` stable; never rename IDs after publication.
- Approved initiatives without `solution_repo_url` must not be published to selector.

## Typical Commands

One-step intake + selector regeneration:

```bash
python scripts/intake_and_generate_selector.py \
  --pipeline architecture/portfolio/initiative-pipeline.yml \
  --out architecture/portfolio/initiatives.yml \
  --initiative-id init-bss-modernization \
  --name "BSS Modernization" \
  --stage approved_for_delivery \
  --description "Modernize BSS stack and retire duplicate legacy platforms." \
  --objective "Reduce order-to-activate lead time by 30%." \
  --objective "Consolidate TMF API surface across domains." \
  --pm-owner pm-team-a \
  --it-owner sa-team-a \
  --solution-repo-url https://github.com/<org>/<solution-repo> \
  --publish-to-selector true \
  --selector-status active
```

With auto push:

```bash
python scripts/intake_and_generate_selector.py \
  --pipeline architecture/portfolio/initiative-pipeline.yml \
  --out architecture/portfolio/initiatives.yml \
  --initiative-id init-bss-modernization \
  --name "BSS Modernization" \
  --stage approved_for_delivery \
  --description "Modernize BSS stack and retire duplicate legacy platforms." \
  --objective "Reduce order-to-activate lead time by 30%." \
  --pm-owner pm-team-a \
  --it-owner sa-team-a \
  --solution-repo-url https://github.com/<org>/<solution-repo> \
  --publish-to-selector true \
  --selector-status active \
  --auto-git-push \
  --git-commit-message "portfolio: publish init-bss-modernization"
```

Upsert only:

```bash
python scripts/upsert_initiative_pipeline.py \
  --pipeline architecture/portfolio/initiative-pipeline.yml \
  --initiative-id init-bss-modernization \
  --name "BSS Modernization" \
  --stage approved_for_delivery \
  --description "Modernize BSS stack and retire duplicate legacy platforms." \
  --objective "Reduce order-to-activate lead time by 30%." \
  --objective "Consolidate TMF API surface across domains." \
  --pm-owner pm-team-a \
  --it-owner sa-team-a \
  --solution-repo-url https://github.com/<org>/<solution-repo> \
  --publish-to-selector true \
  --selector-status active
```

```bash
python ../enterprise-architecture/scripts/generate_initiatives_selector.py \
  --pipeline architecture/portfolio/initiative-pipeline.yml \
  --out architecture/portfolio/initiatives.yml
```
