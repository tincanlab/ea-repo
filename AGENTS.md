# AGENTS

Role: ea
Instruction: Read `ENTERPRISE.md` first (mandatory entrypoint).
Guardrail: `ENTERPRISE.md` is a critical contract file. Preserve template section structure and keep mutable operational detail in linked canonical artifacts.
Navigation: When looking up a repo referenced by `solution_repo_url`, use the URL directly (e.g. fetch the GitHub URL). Do not search the local filesystem — solution repos are external and the URL is the authoritative pointer.
