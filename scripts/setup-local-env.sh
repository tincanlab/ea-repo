#!/usr/bin/env bash
# setup-local-env.sh — load and validate local env for EA/SA/DA skills
# Works with any AI coding tool: opencode, Claude Code (claude), Codex, etc.
#
# Usage (must be sourced, not executed):
#   source scripts/setup-local-env.sh ea
#   source scripts/setup-local-env.sh sa
#   source scripts/setup-local-env.sh da
#
# Then start your tool of choice:
#   opencode
#   claude
#   codex
#
# Optionally render opencode.json first (only needed for opencode):
#   bash scripts/render-opencode-config.sh

set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT="$(cd "$_SCRIPT_DIR/.." && pwd)"

_usage() {
  echo "Usage: source scripts/setup-local-env.sh <role>" >&2
  echo "  role: ea | sa | da" >&2
  return 1
}

_ROLE="${1:-}"
if [[ -z "$_ROLE" ]]; then
  _usage
fi

case "$_ROLE" in
  ea|sa|da) ;;
  *) echo "ERROR: unknown role '$_ROLE'. Must be ea, sa, or da." >&2; _usage ;;
esac

_ENV_FILE="$_REPO_ROOT/.env.${_ROLE}.local"
_ENV_EXAMPLE="$_REPO_ROOT/.env.${_ROLE}.local.example"

if [[ ! -f "$_ENV_FILE" ]]; then
  echo "ERROR: $_ENV_FILE not found." >&2
  echo "  Copy the example and fill in your values:" >&2
  echo "    cp $_ENV_EXAMPLE $_ENV_FILE" >&2
  echo "    \$EDITOR $_ENV_FILE" >&2
  return 1
fi

# Load env file (skip blank lines and comments)
set -o allexport
# shellcheck disable=SC1090
source "$_ENV_FILE"
set +o allexport

# Default GIT_WORKDIR to repo root when not set
if [[ -z "${OPENARCHITECT_GIT_WORKDIR:-}" ]]; then
  export OPENARCHITECT_GIT_WORKDIR="$_REPO_ROOT"
fi

# Set role
export OPENARCHITECT_CONTAINER_ROLE="$_ROLE"

# Validate required vars per role
_missing=()
[[ -z "${GITHUB_TOKEN:-}"       ]] && _missing+=("GITHUB_TOKEN")
[[ -z "${TMF_MCP_URL:-}"        ]] && _missing+=("TMF_MCP_URL")
[[ -z "${POSTGRES_MCP_URL:-}"   ]] && _missing+=("POSTGRES_MCP_URL")

case "$_ROLE" in
  ea)
    [[ -z "${OPENARCHITECT_EA_REPO_URL:-}" ]] && _missing+=("OPENARCHITECT_EA_REPO_URL")
    ;;
  sa)
    [[ -z "${OPENARCHITECT_EA_REPO_URL:-}" ]] && _missing+=("OPENARCHITECT_EA_REPO_URL")
    [[ -z "${INITIATIVE_ID:-}"             ]] && _missing+=("INITIATIVE_ID")
    ;;
  da)
    [[ -z "${OPENARCHITECT_SA_REPO_URL:-}" ]] && _missing+=("OPENARCHITECT_SA_REPO_URL")
    [[ -z "${WORKSTREAM_ID:-}"             ]] && _missing+=("WORKSTREAM_ID")
    ;;
esac

if [[ ${#_missing[@]} -gt 0 ]]; then
  echo "ERROR: missing required variables in $_ENV_FILE:" >&2
  for _v in "${_missing[@]}"; do
    echo "  - $_v" >&2
  done
  return 1
fi

# Override config template paths for local use
export OPENCODE_CONFIG_TEMPLATE="$_REPO_ROOT/opencode.json.template"
export OPENCODE_PROJECT_CONFIG_PATH="$_REPO_ROOT/opencode.json"

echo "Local env loaded:"
echo "  role=$_ROLE"
echo "  workdir=$OPENARCHITECT_GIT_WORKDIR"
echo ""
echo "Start your tool of choice:"
echo "  opencode   (also run render-opencode-config.sh first to render opencode.json)"
echo "  claude"
echo "  codex"
