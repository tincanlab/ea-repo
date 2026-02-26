#!/usr/bin/env bash
set -euo pipefail

CONFIG_TEMPLATE="${OPENCODE_CONFIG_TEMPLATE:-/home/op/project/opencode.json.template}"
PROJECT_CONFIG_PATH="${OPENCODE_PROJECT_CONFIG_PATH:-/home/op/project/opencode.json}"

: "${TMF_MCP_URL:?TMF_MCP_URL is required}"
: "${POSTGRES_MCP_URL:?POSTGRES_MCP_URL is required}"
: "${MODEL:=opencode/minimax-m2.5-free}"
: "${AUTH_PROVIDER:=zai-coding-plan}"
: "${API_KEY:=}"
: "${OPENARCHITECT_GIT_WORKDIR:=/home/op/project}"
: "${GITHUB_HOST:=github.com}"

is_placeholder_value() {
  local value="$1"
  case "$value" in
    *__REQUIRED_*|*\<*|*\>*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

require_real_repo_url_env() {
  local var_name="$1"
  local value="${!var_name:-}"
  if [ -n "$value" ] && is_placeholder_value "$value"; then
    echo "ERROR: $var_name uses a placeholder value ('$value'). Set it to a real GitHub repo URL." >&2
    exit 1
  fi
}

# Configure GitHub credentials before any selector fetch from remote repos.
# Note: relying on credential helpers alone can be flaky in non-interactive container runs.
# We do both:
# 1) credential approve (so helpers like credential-cache can serve it)
# 2) a URL rewrite so https clones/fetches always pick up the token.
GITHUB_AUTH_TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
if [ -n "${GITHUB_AUTH_TOKEN:-}" ]; then
  echo "protocol=https
host=${GITHUB_HOST}
username=x-access-token
password=${GITHUB_AUTH_TOKEN}" | git credential approve || true

  # Ensure https://<host>/... uses the token without prompts.
  git config --global url."https://x-access-token:${GITHUB_AUTH_TOKEN}@${GITHUB_HOST}/".insteadOf "https://${GITHUB_HOST}/"
  if [ "${GITHUB_HOST}" != "github.com" ]; then
    git config --global url."https://x-access-token:${GITHUB_AUTH_TOKEN}@${GITHUB_HOST}/".insteadOf "https://github.com/"
  fi
fi

require_real_repo_url_env OPENARCHITECT_EA_REPO_URL
require_real_repo_url_env OPENARCHITECT_SA_REPO_URL
require_real_repo_url_env OPENARCHITECT_SELECTOR_SOURCE_REPO_URL
require_real_repo_url_env OPENARCHITECT_GIT_REPO_URL

ROUTING_ROLE=""
if [ -n "${OPENARCHITECT_CONTAINER_ROLE:-}" ]; then
  case "${OPENARCHITECT_CONTAINER_ROLE}" in
    sa|da|dev|ea)
      ROUTING_ROLE="${OPENARCHITECT_CONTAINER_ROLE}"
      ;;
    *)
      echo "WARNING: unrecognized OPENARCHITECT_CONTAINER_ROLE=${OPENARCHITECT_CONTAINER_ROLE}" >&2
      ;;
  esac
fi

if [ -z "${OPENARCHITECT_EA_REPO_URL:-}" ] && [ -n "${GITHUB_OWNER:-}" ]; then
  OPENARCHITECT_EA_REPO_URL="https://${GITHUB_HOST}/${GITHUB_OWNER}/ea-repo"
fi

if [ "${ROUTING_ROLE:-}" = "ea" ] && [ -n "${OPENARCHITECT_EA_REPO_URL:-}" ]; then
  # EA role convention: target the EA repo derived/provided by OPENARCHITECT_EA_REPO_URL.
  OPENARCHITECT_GIT_REPO_URL="${OPENARCHITECT_EA_REPO_URL}"
elif [ -z "${OPENARCHITECT_GIT_REPO_URL:-}" ] && [ -n "${OPENARCHITECT_EA_REPO_URL:-}" ]; then
  OPENARCHITECT_GIT_REPO_URL="$OPENARCHITECT_EA_REPO_URL"
fi

if [ ! -f "$CONFIG_TEMPLATE" ]; then
  echo "Config template not found: $CONFIG_TEMPLATE" >&2
  exit 1
fi

mkdir -p "$(dirname "$PROJECT_CONFIG_PATH")"
cp "$CONFIG_TEMPLATE" "$PROJECT_CONFIG_PATH"

SELECTOR_FETCH_DIRS=()
EFFECTIVE_SELECTOR_CATALOG=""
EFFECTIVE_SELECTOR_SOURCE_REPO_URL=""
EFFECTIVE_DA_ENGAGEMENT_CATALOG=""

cleanup_selector_fetch_dirs() {
  for fetch_dir in "${SELECTOR_FETCH_DIRS[@]}"; do
    if [ -n "$fetch_dir" ] && [ -d "$fetch_dir" ]; then
      rm -rf "$fetch_dir"
    fi
  done
}

ensure_git_workdir_repo() {
  local workdir="${OPENARCHITECT_GIT_WORKDIR:-/home/op/project}"
  mkdir -p "$workdir"
  if [ -d "$workdir/.git" ]; then
    echo "Git repository already initialized:"
    echo "  - $workdir/.git"
    return 0
  fi

  git -C "$workdir" init >/dev/null
  echo "Initialized git repository:"
  echo "  - $workdir/.git"
}

render_role_agents_md() {
  local role="${1:-}"
  local workdir="${OPENARCHITECT_GIT_WORKDIR:-/home/op/project}"
  local file_path="$workdir/AGENTS.md"
  local start_marker="<!-- OPENARCHITECT_ROLE_CONTEXT_START -->"
  local end_marker="<!-- OPENARCHITECT_ROLE_CONTEXT_END -->"
  local context_file="AGENTS.md"

  mkdir -p "$workdir"
  touch "$file_path"

  # Remove prior generated role block while preserving all other file content.
  awk -v s="$start_marker" -v e="$end_marker" '
    $0==s {skip=1; next}
    $0==e {skip=0; next}
    !skip {print}
  ' "$file_path" > "${file_path}.tmp"
  mv "${file_path}.tmp" "$file_path"

  {
    echo "$start_marker"
    echo "## OpenArchitect Role Context (Auto-generated)"
    case "$role" in
      ea) context_file="ENTERPRISE.md" ;;
      sa) context_file="SOLUTION.md" ;;
      da) context_file="DOMAIN.md" ;;
      dev) context_file="DOMAIN.md" ;;
      *) context_file="AGENTS.md" ;;
    esac
    echo ""
    echo "role: ${role:-unknown}"
    echo "context_file: ${context_file}"
    echo "instruction: Read \`${context_file}\` for role architecture context. Keep \`AGENTS.md\` for general agent behavior/policy."
    if [ "$role" = "ea" ]; then
      echo "fallback: If \`${context_file}\` is missing, run quick-start (EA profile) to sync/hydrate or validate the repo."
      echo "  python .opencode/skills/openarchitect/quick-start/scripts/run_quick_start.py --root . --profile ea --sync-from-github --github-repo-url \"${OPENARCHITECT_EA_REPO_URL:-${OPENARCHITECT_GIT_REPO_URL:-}}\""
    else
      echo "fallback: If \`${context_file}\` is missing, run quick-start to validate your working directory is a real repo with the expected entrypoints."
      echo "  python .opencode/skills/openarchitect/quick-start/scripts/run_quick_start.py --root ."
    fi
    echo "$end_marker"
  } >> "$file_path"

  echo "Role context written:"
  echo "  - $file_path"
}

resolve_selector_catalog_path() {
  local role="$1"
  local catalog_rel="${OPENARCHITECT_SELECTOR_CATALOG:-}"
  local engagement_rel="${OPENARCHITECT_DA_ENGAGEMENT_CATALOG:-architecture/solution/domain-engagements.yml}"
  local source_ref="${OPENARCHITECT_SELECTOR_SOURCE_REF:-}"
  local fetch_dir=""

  if [ -z "$catalog_rel" ]; then
    case "$role" in
      sa) catalog_rel="architecture/portfolio/initiatives.yml" ;;
      da) catalog_rel="$engagement_rel" ;;
      *) catalog_rel="" ;;
    esac
  fi

  EFFECTIVE_SELECTOR_SOURCE_REPO_URL="${OPENARCHITECT_SELECTOR_SOURCE_REPO_URL:-}"
  if [ -z "${EFFECTIVE_SELECTOR_SOURCE_REPO_URL:-}" ] && [ "$role" = "sa" ] && [ -n "${OPENARCHITECT_EA_REPO_URL:-}" ]; then
    EFFECTIVE_SELECTOR_SOURCE_REPO_URL="${OPENARCHITECT_EA_REPO_URL}"
  fi
  if [ -z "${EFFECTIVE_SELECTOR_SOURCE_REPO_URL:-}" ] && [ "$role" = "da" ] && [ -n "${OPENARCHITECT_SA_REPO_URL:-}" ]; then
    EFFECTIVE_SELECTOR_SOURCE_REPO_URL="${OPENARCHITECT_SA_REPO_URL}"
  fi
  if [ -n "${EFFECTIVE_SELECTOR_SOURCE_REPO_URL:-}" ] && is_placeholder_value "${EFFECTIVE_SELECTOR_SOURCE_REPO_URL}"; then
    echo "ERROR: selector source repo URL is a placeholder: ${EFFECTIVE_SELECTOR_SOURCE_REPO_URL}" >&2
    exit 1
  fi

  if [ -z "$catalog_rel" ] || [ -z "${EFFECTIVE_SELECTOR_SOURCE_REPO_URL:-}" ]; then
    EFFECTIVE_SELECTOR_CATALOG="$catalog_rel"
    return 0
  fi

  if [[ "$catalog_rel" = /* ]]; then
    echo "ERROR: selector catalog must be a repo-relative path when OPENARCHITECT_SELECTOR_SOURCE_REPO_URL/OPENARCHITECT_EA_REPO_URL is used: $catalog_rel" >&2
    exit 1
  fi

  fetch_dir="$(mktemp -d /tmp/oa-selector.XXXXXX)"
  SELECTOR_FETCH_DIRS+=("$fetch_dir")

  if ! git clone --depth 1 --filter=blob:none "${EFFECTIVE_SELECTOR_SOURCE_REPO_URL}" "$fetch_dir" >/dev/null 2>&1; then
    echo "ERROR: failed to clone selector source repo: ${EFFECTIVE_SELECTOR_SOURCE_REPO_URL}" >&2
    exit 1
  fi

  if [ -n "$source_ref" ] && [ "$source_ref" != "HEAD" ]; then
    if ! git -C "$fetch_dir" fetch --depth 1 origin "$source_ref" >/dev/null 2>&1; then
      echo "ERROR: failed to fetch selector source ref '$source_ref' from ${EFFECTIVE_SELECTOR_SOURCE_REPO_URL}" >&2
      exit 1
    fi
    if ! git -C "$fetch_dir" checkout --quiet FETCH_HEAD >/dev/null 2>&1; then
      echo "ERROR: failed to checkout selector source ref '$source_ref' from ${EFFECTIVE_SELECTOR_SOURCE_REPO_URL}" >&2
      exit 1
    fi
  fi

  if [ "$role" = "da" ] && [ -z "${OPENARCHITECT_SELECTOR_CATALOG:-}" ]; then
    EFFECTIVE_DA_ENGAGEMENT_CATALOG="$fetch_dir/$engagement_rel"
    if [ ! -f "$EFFECTIVE_DA_ENGAGEMENT_CATALOG" ]; then
      echo "ERROR: DA engagement selector '$engagement_rel' not found in selector source repo ${EFFECTIVE_SELECTOR_SOURCE_REPO_URL}" >&2
      exit 1
    fi
    return 0
  fi

  EFFECTIVE_SELECTOR_CATALOG="$fetch_dir/$catalog_rel"
  if [ ! -f "$EFFECTIVE_SELECTOR_CATALOG" ]; then
    echo "ERROR: selector catalog '$catalog_rel' not found in selector source repo ${EFFECTIVE_SELECTOR_SOURCE_REPO_URL}" >&2
    exit 1
  fi
}

trap cleanup_selector_fetch_dirs EXIT

# Resolve repo target from selector manifests when role-based routing is enabled.
if [ "${ROUTING_ROLE:-}" = "ea" ]; then
  echo "Selector resolution skipped for EA role."
elif [ -n "${ROUTING_ROLE:-}" ]; then
  RESOLVE_CMD=(python3 /home/op/project/scripts/resolve_container_git_target.py
    --role "$ROUTING_ROLE"
    --output export
    --git-workdir "$OPENARCHITECT_GIT_WORKDIR")
  if [ -n "${OPENARCHITECT_SELECTOR_ID:-}" ]; then
    RESOLVE_CMD+=(--selector-id "$OPENARCHITECT_SELECTOR_ID")
  fi

  if [ "${ROUTING_ROLE}" = "sa" ] || [ "${ROUTING_ROLE}" = "da" ]; then
    resolve_selector_catalog_path "${ROUTING_ROLE}"
    if [ "${ROUTING_ROLE}" = "da" ] && [ -n "${EFFECTIVE_DA_ENGAGEMENT_CATALOG:-}" ]; then
      RESOLVE_CMD+=(--da-engagement-catalog "$EFFECTIVE_DA_ENGAGEMENT_CATALOG")
    fi
    if [ -n "${EFFECTIVE_SELECTOR_CATALOG:-}" ]; then
      RESOLVE_CMD+=(--catalog "$EFFECTIVE_SELECTOR_CATALOG")
    fi
  elif [ -n "${OPENARCHITECT_SELECTOR_CATALOG:-}" ]; then
    RESOLVE_CMD+=(--catalog "$OPENARCHITECT_SELECTOR_CATALOG")
  fi
  if [ -n "${OPENARCHITECT_SELECTOR_IMPLEMENTATION_CATALOG:-}" ]; then
    RESOLVE_CMD+=(--implementation-catalog "$OPENARCHITECT_SELECTOR_IMPLEMENTATION_CATALOG")
  fi
  if [ "${OPENARCHITECT_SELECTOR_ALLOW_INACTIVE:-false}" = "true" ]; then
    RESOLVE_CMD+=(--allow-inactive)
  fi
  eval "$("${RESOLVE_CMD[@]}")"
  echo "Selector resolved:"
  echo "  - role=${ROUTING_ROLE}"
  echo "  - selector_id=${OPENARCHITECT_SELECTOR_ID:-${INITIATIVE_ID:-${ENGAGEMENT_ID:-${WORK_ITEM_ID:-${API_ID:-}}}}}"
  if [ -n "${OPENARCHITECT_SELECTOR_KIND:-}" ]; then
    echo "  - selector_kind=${OPENARCHITECT_SELECTOR_KIND}"
  fi
  if [ -n "${EFFECTIVE_SELECTOR_CATALOG:-}" ]; then
    echo "  - selector_catalog=${EFFECTIVE_SELECTOR_CATALOG}"
  fi
  if [ -n "${EFFECTIVE_DA_ENGAGEMENT_CATALOG:-}" ]; then
    echo "  - da_engagement_catalog=${EFFECTIVE_DA_ENGAGEMENT_CATALOG}"
  fi
  if [ -n "${EFFECTIVE_SELECTOR_SOURCE_REPO_URL:-}" ]; then
    echo "  - selector_source_repo=${EFFECTIVE_SELECTOR_SOURCE_REPO_URL}"
  fi
  echo "  - repo_url=${OPENARCHITECT_GIT_REPO_URL:-<none>}"
fi

ensure_git_workdir_repo

if [ "${OPENARCHITECT_CONTAINER_ROLE:-}" = "ea" ] && [ -z "${OPENARCHITECT_GIT_REPO_URL:-}" ]; then
  echo "WARNING: EA role started without OPENARCHITECT_GIT_REPO_URL/OPENARCHITECT_EA_REPO_URL; GitHub compare/sync features will be disabled." >&2
fi

if [ -n "${ROUTING_ROLE:-}" ]; then
  render_role_agents_md "$ROUTING_ROLE"
fi

write_active_initiative_context() {
  local workdir="${OPENARCHITECT_GIT_WORKDIR:-/home/op/project}"
  local context_json="${OPENARCHITECT_ACTIVE_INITIATIVE_CONTEXT_JSON:-}"
  if [ -z "$context_json" ]; then
    return 0
  fi
  mkdir -p "$workdir/.openarchitect"
  printf '%s\n' "$context_json" > "$workdir/.openarchitect/active-initiative.json"
  echo "Active initiative context written:"
  echo "  - $workdir/.openarchitect/active-initiative.json"
}

if [ "${ROUTING_ROLE:-}" = "sa" ]; then
  write_active_initiative_context
fi

escape() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

sed -i \
  -e "s/__TMF_MCP_URL__/$(escape "$TMF_MCP_URL")/g" \
  -e "s/__POSTGRES_MCP_URL__/$(escape "$POSTGRES_MCP_URL")/g" \
  -e "s/__OPENCODE_MODEL__/$(escape "$MODEL")/g" \
  "$PROJECT_CONFIG_PATH"

# Keep project config as the single source of truth.
GLOBAL_CONFIG_PATH="/home/op/.config/opencode/opencode.json"
if [ -f "$GLOBAL_CONFIG_PATH" ]; then
  rm -f "$GLOBAL_CONFIG_PATH"
fi

AUTH_TEMPLATE="/home/op/project/auth.json.template"
AUTH_PATH="/home/op/.local/share/opencode/auth.json"
if [ -f "$AUTH_TEMPLATE" ] && [ -n "$API_KEY" ]; then
  mkdir -p "$(dirname "$AUTH_PATH")"
  cp "$AUTH_TEMPLATE" "$AUTH_PATH"
  sed -i \
    -e "s/__OPENCODE_AUTH_PROVIDER__/$(escape "$AUTH_PROVIDER")/g" \
    -e "s/__OPENCODE_AUTH_KEY__/$(escape "$API_KEY")/g" \
    "$AUTH_PATH"
  echo "Rendered auth config:"
  echo "  - $AUTH_PATH"
fi

echo "Rendered opencode configs:"
echo "  - $PROJECT_CONFIG_PATH"
