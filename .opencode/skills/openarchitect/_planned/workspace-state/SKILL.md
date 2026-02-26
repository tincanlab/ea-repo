---
name: workspace-state
description: Planned utility skill for local workspace selection/state persistence via `.openarchitect/local.yml`.
---

# Workspace State (Planned)

## Status

This capability is intentionally moved out of active skills and parked under `_planned`.

## Purpose

Use these scripts only when local workspace selection persistence is explicitly needed:

- `_planned/workspace-state/<skill>/scripts/persist_local_state.py`

## Notes

- Active skills should remain Git-first by default and avoid local workspace state coupling.
- This capability is separate from artifact registration (see `_planned/workspace-registration`).
