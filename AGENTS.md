<!-- OPENARCHITECT_ROLE_CONTEXT_START -->
## OpenArchitect Role Context (Auto-generated)

role: ea
context_file: ENTERPRISE.md
instruction: Read `ENTERPRISE.md` for role architecture context. Keep `AGENTS.md` for general agent behavior/policy.
fallback: If `ENTERPRISE.md` is missing, run quick-start (EA profile) to sync/hydrate or validate the repo.
  python .opencode/skills/openarchitect/quick-start/scripts/run_quick_start.py --root . --profile ea --sync-from-github --github-repo-url "https://github.com/tincanlab/ea-repo"
<!-- OPENARCHITECT_ROLE_CONTEXT_END -->
