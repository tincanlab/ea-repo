---
name: repo-creation
description: Create governed repository creation requests and optional GitHub repositories. Use when solution architecture outputs identify required repos, when checking if target repos already exist, when preparing approval-ready repo provisioning artifacts, or when executing approved repo creation and updating Git manifests.
---

# Repo Creation

## Overview

This skill handles repository provisioning as a governed flow:
- confirm what repos are required (usually from SA outputs)
- check current Git manifests and GitHub existence
- produce approval-ready creation requests
- optionally execute approved creation
- update repo-root `solution-index.yml` (Git-authoritative scope manifest)

This skill assumes repo policy is static and platform-managed. It does not require EA sign-off by default.

## Repository Convention

- Primary inputs from SA:
  - `architecture/solution/repo-plan.yml`
  - `architecture/solution/repo-creation-request.yml`
- Primary outputs:
  - `architecture/solution/repo-creation-request.yml` (updated state)
  - `architecture/solution/repo-creation-result.yml` (execution result)
  - `solution-index.yml` (updated repo list, Git-only / Git-authoritative)
  - Optional: `architecture/solution/repo-creation-result.md` (human summary)

Repo keys (recommended):
- `solution_design` (this solution repo)
- `domain_<domain_key>` (TMF ODA component repo)
- `api_<api_id>` (implementation repo for a specific API, if split out)
- `infra_<purpose>` (optional infra/ops repo)

Use templates:
- `references/repo-creation-request.yml.template`
- `references/repo-creation-result.yml.template`

## Required Inputs

- target GitHub owner (user or org)
- requested repos (from SA artifact or user)

Optional:
- `default_repo_key` for solution default-repo selection
- visibility override (`private` default)

## Tooling and Access

Git-first mode:
- no MCP required
- local scripts: `scripts/execute_repo_creation.py`, `scripts/github_repo_check.py`, `scripts/github_repo_create.py`, `scripts/update_solution_index.py`
- GitHub creation path policy:
  - prefer `gh` CLI for interactive/manual operations when available (`gh auth status` should pass)
  - scripts default to GitHub REST calls via `curl` to avoid requiring `gh` in minimal/containerized environments

GitHub auth:
- `GITHUB_TOKEN` with repo creation/admin scope as needed.
- If token is missing, run request-only mode and set `execution.state=blocked_no_credentials`.

## Workflow

### Phase 0: Load Inputs

1. Load requested repos:
- prefer `architecture/solution/repo-creation-request.yml`
- fallback to `architecture/solution/repo-plan.yml`
- if both missing, ask user for requested repos and create a new request file

### Phase 1: Verify Existing Repos

2. Check current solution-index coverage:
- inspect `solution-index.yml` and mark each requested repo as `indexed` / `not_indexed`

3. Check GitHub existence:
- run `scripts/github_repo_check.py --owner <owner> --repo <name>...`
- capture per-repo status: `exists`, `missing`, `error`

4. Update request artifact:
- set each repo `current_state` with solution-index + GitHub check evidence
- if repo already exists and is suitable, set action `map_only`
- if missing, set action `create_then_map`

### Phase 2: Approval Package

5. Emit/refresh `repo-creation-request.yml`:
- include reason, owner, name, visibility, and default-repo flag (`default_for_solution`; legacy `default_for_workspace` alias accepted)
- include `approval.state` and `requested_by`
- include `source_artifacts` (`repo_plan`, `architecture_design`) when available

6. Stop for approval when required:
- unless explicitly told to execute, leave `execution.state=not_started`
- never claim a repo was created without tool evidence

### Phase 3: Execute (Only When Explicitly Approved)

7. Execute end-to-end flow:
- run `scripts/execute_repo_creation.py` (single command):
  - reads `repo-creation-request.yml`
  - checks/creates repos on GitHub (based on `action`)
  - repo creation is executed via `scripts/github_repo_create.py` (REST API via `curl`, by design to avoid mandatory `gh` dependency)
  - writes `repo-creation-result.yml`
  - updates `solution-index.yml` (unless `--skip-solution-index-update`)
- collect JSON summary and evidence from script output

Direct creation call shapes (reference):
```bash
# gh (interactive/manual preferred when available)
gh repo create <owner>/<repo> --private --description "<description>"

# curl (script/container fallback; no gh dependency)
curl -sS -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/orgs/<owner>/repos \
  -d '{"name":"<repo>","private":true,"description":"<description>"}'
```

Example:
```bash
python scripts/execute_repo_creation.py --request architecture/solution/repo-creation-request.yml --result architecture/solution/repo-creation-result.yml --solution-index solution-index.yml
```

8. Emit result artifact:
- write `architecture/solution/repo-creation-result.yml`
- set `execution.state` to `completed`, `partial_failure`, or `failed`
- include created repo URLs, mapped repos, and failures

### Phase 4: Update Git Manifests (Git-only / Git-authoritative)

9. Upsert `solution-index.yml` repo list (in the solution repo root):
- normally handled inside `scripts/execute_repo_creation.py`
- run `scripts/update_solution_index.py` directly only when manual reconciliation is required
- prefer running after Phase 3 so the result can filter out failures

Example:
```bash
python scripts/update_solution_index.py --solution-index solution-index.yml --request architecture/solution/repo-creation-request.yml --result architecture/solution/repo-creation-result.yml
```

## Output Contract

Use `references/repo-creation-request.yml.template` and `references/repo-creation-result.yml.template`.

Minimum request fields:
- `request_id`
- `repos_requested[]` with `repo_key`, `owner`, `name`, `visibility`, `default_for_solution`, `reason` (legacy `default_for_workspace` accepted)
- Optional: `repos_requested[].purpose` (used to populate `solution-index.yml` repo entries)
- `approval.state`
- `execution.state`

Minimum result fields:
- `request_id`
- `execution.state`
- `created_repos[]`
- `mapped_repos[]`
- `failures[]`

## Truthfulness and Safety

- Do not claim repo creation success without GitHub API/script evidence.
- Do not silently change default repo selection; set it explicitly and record why.
- Do not auto-escalate governance roles; follow the environment's access controls.
- If credentials are missing or insufficient, output a complete request artifact and stop cleanly.
## Execution Prompt Assets

- agents/sub-agents.yaml (capability and routing contract)
- agents/prompts/orchestrator.md (workflow controller prompt)
- agents/prompts/*.md (specialist prompt bodies)
