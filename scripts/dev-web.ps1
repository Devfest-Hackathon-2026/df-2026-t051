$ErrorActionPreference = 'Stop'
Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) 'frontend')
if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    pnpm dev
} else {
    $bundledPnpm = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\pnpm\bin\pnpm.cjs'
    if (-not (Test-Path -LiteralPath $bundledPnpm)) { throw 'pnpm 11.25.0 is required.' }
    node $bundledPnpm dev
}
