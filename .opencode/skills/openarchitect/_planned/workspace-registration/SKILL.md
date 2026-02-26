---
name: workspace-registration
description: Planned utility skill for registering local artifacts into the OpenArchitect workspace database (Context Registry).
---

# Workspace Registration (Planned)

## Status

This capability is intentionally moved out of active skills and parked under `_planned`.

## Purpose

Use these scripts only when database-backed workspace artifact registration is explicitly enabled:

- `_planned/workspace-registration/common/scripts/register_workspace_artifacts.py`
- `_planned/workspace-registration/<skill>/scripts/register_workspace_artifacts.py`

## Notes

- These scripts require the `openarchitect` runtime package and database connectivity.
- Active skills should stay Git-first and not depend on DB registration paths.
