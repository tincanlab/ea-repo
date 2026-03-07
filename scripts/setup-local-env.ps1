# setup-local-env.ps1 — load and validate local env for EA/SA/DA skills
# Works with any AI coding tool: opencode, Claude Code (claude), Codex, etc.
#
# Usage (must be dot-sourced to export vars into current session):
#   . .\scripts\setup-local-env.ps1 ea
#   . .\scripts\setup-local-env.ps1 sa
#   . .\scripts\setup-local-env.ps1 da
#
# Then start your tool of choice:
#   opencode
#   claude
#   codex
#
# Optionally render opencode.json first (only needed for opencode):
#   bash scripts/render-opencode-config.sh

param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("ea","sa","da")]
    [string]$Role
)

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot   = Split-Path -Parent $ScriptDir
$EnvFile    = Join-Path $RepoRoot ".env.$Role.local"
$EnvExample = Join-Path $RepoRoot ".env.$Role.local.example"

if (-not (Test-Path $EnvFile)) {
    Write-Error "Not found: $EnvFile`n  Copy the example and fill in your values:`n    Copy-Item '$EnvExample' '$EnvFile'`n    notepad '$EnvFile'"
    return
}

# Parse and export KEY=VALUE lines (skip blanks and comments)
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { return }
    $key   = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim()
    # Strip surrounding quotes if present
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    Set-Item -Path "Env:$key" -Value $value
}

# Default GIT_WORKDIR to repo root when not set
if (-not $env:OPENARCHITECT_GIT_WORKDIR) {
    $env:OPENARCHITECT_GIT_WORKDIR = $RepoRoot
    [System.Environment]::SetEnvironmentVariable("OPENARCHITECT_GIT_WORKDIR", $RepoRoot, "Process")
}

# Set role
$env:OPENARCHITECT_CONTAINER_ROLE = $Role
[System.Environment]::SetEnvironmentVariable("OPENARCHITECT_CONTAINER_ROLE", $Role, "Process")

# Set config template paths for local use
$env:OPENCODE_CONFIG_TEMPLATE      = Join-Path $RepoRoot "opencode.json.template"
$env:OPENCODE_PROJECT_CONFIG_PATH  = Join-Path $RepoRoot "opencode.json"
[System.Environment]::SetEnvironmentVariable("OPENCODE_CONFIG_TEMPLATE",     $env:OPENCODE_CONFIG_TEMPLATE,     "Process")
[System.Environment]::SetEnvironmentVariable("OPENCODE_PROJECT_CONFIG_PATH", $env:OPENCODE_PROJECT_CONFIG_PATH, "Process")

# Validate required vars per role
$missing = @()
if (-not $env:GITHUB_TOKEN)     { $missing += "GITHUB_TOKEN" }
if (-not $env:TMF_MCP_URL)      { $missing += "TMF_MCP_URL" }
if (-not $env:POSTGRES_MCP_URL) { $missing += "POSTGRES_MCP_URL" }

switch ($Role) {
    "ea" {
        if (-not $env:OPENARCHITECT_EA_REPO_URL) { $missing += "OPENARCHITECT_EA_REPO_URL" }
    }
    "sa" {
        if (-not $env:OPENARCHITECT_EA_REPO_URL) { $missing += "OPENARCHITECT_EA_REPO_URL" }
        if (-not $env:INITIATIVE_ID)             { $missing += "INITIATIVE_ID" }
    }
    "da" {
        if (-not $env:OPENARCHITECT_SA_REPO_URL) { $missing += "OPENARCHITECT_SA_REPO_URL" }
        if (-not $env:WORKSTREAM_ID)             { $missing += "WORKSTREAM_ID" }
    }
}

if ($missing.Count -gt 0) {
    Write-Error "Missing required variables in $EnvFile`:`n$(($missing | ForEach-Object { "  - $_" }) -join "`n")"
    return
}

Write-Host "Local env loaded:"
Write-Host "  role=$Role"
Write-Host "  workdir=$env:OPENARCHITECT_GIT_WORKDIR"
Write-Host ""
Write-Host "Start your tool of choice:"
Write-Host "  opencode   (also run 'bash scripts/render-opencode-config.sh' first to render opencode.json)"
Write-Host "  claude"
Write-Host "  codex"
