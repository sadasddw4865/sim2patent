# ============================================================================
# sim2patent -> GitHub one-shot upload (uses GitHub CLI: gh)
#
# What it does:
#   1. sanity checks (git + gh installed)
#   2. checks gh authentication (run `gh auth login` if needed)
#   3. ensures a git repo with main branch + initial commit
#   4. creates PUBLIC repo "<your-account>/<RepoName>" if needed
#   5. pushes to origin
#
# Usage (from anywhere):
#   powershell -ExecutionPolicy Bypass -File scripts\upload-github.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\upload-github.ps1 -RepoName sim2patent
#
# Prereqs:
#   - git installed
#   - GitHub CLI installed and authenticated:  gh auth login
#   - git identity configured:
#         git config --global user.name  "Your Name"
#         git config --global user.email "you@example.com"
# ============================================================================

param(
    [string]$RepoName   = "sim2patent",
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot   # scripts/ -> repository root
Set-Location $Root

# --- 1) tools --------------------------------------------------------------
foreach ($tool in @("git", "gh")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "[ERR] '$tool' not found. Install it first." -ForegroundColor Red
        exit 1
    }
}

# --- 2) gh authentication ---------------------------------------------------
gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERR] GitHub CLI is not authenticated." -ForegroundColor Red
    Write-Host "       Run:  gh auth login" -ForegroundColor Yellow
    exit 1
}
$Account = (gh api user --jq .login | Out-String).Trim()
Write-Host "[ok] authenticated as: $Account" -ForegroundColor Green

# --- 3) git identity ---------------------------------------------------------
git config --get user.name  *> $null
$hasName = ($LASTEXITCODE -eq 0)
git config --get user.email *> $null
$hasEmail = ($LASTEXITCODE -eq 0)
if (-not $hasName -or -not $hasEmail) {
    Write-Host "[ERR] git user.name / user.email are not set." -ForegroundColor Red
    Write-Host "       Run:" -ForegroundColor Yellow
    Write-Host "         git config --global user.name  \"Your Name\"" -ForegroundColor Yellow
    Write-Host "         git config --global user.email \"you@example.com\"" -ForegroundColor Yellow
    exit 1
}

# --- 4) init + commit ---------------------------------------------------------
if (-not (Test-Path ".git")) {
    Write-Host "[..] git init -b main" -ForegroundColor Cyan
    git init -b main
}

git add -A
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "[..] nothing staged to commit (already committed?)" -ForegroundColor DarkGray
} else {
    git commit -m "Initial release 0.1.0: simulation-to-patent bridge agent"
}
git branch -M main

# --- 5) create remote repo if needed ------------------------------------------
$RemoteUrl = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[..] creating GitHub repo $Account/$RepoName ($Visibility) ..." -ForegroundColor Cyan
    $ghArgs = @($RepoName, "--source", ".", "--remote", "origin", "--push")
    if ($Visibility -eq "public")  { $ghArgs += "--public" }
    else                           { $ghArgs += "--private" }
    gh repo create @ghArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERR] gh repo create failed." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[..] remote origin exists: $RemoteUrl ; pushing" -ForegroundColor Cyan
    git push -u origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERR] git push failed." -ForegroundColor Red
        exit 1
    }
}

# --- 6) done ------------------------------------------------------------------
Write-Host ""
Write-Host "==============================================================" -ForegroundColor Green
Write-Host " Done: https://github.com/$Account/$RepoName" -ForegroundColor Green
Write-Host " CI will run automatically on the first push." -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Green
