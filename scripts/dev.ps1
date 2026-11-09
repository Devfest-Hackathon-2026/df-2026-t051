param([switch]$Demo)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($Demo) {
    $env:APP_ENV = 'local'
    $env:LOCAL_DEMO = 'true'
} else {
    $env:APP_ENV = 'production'
    $env:LOCAL_DEMO = 'false'
}
# Run frontend in a second terminal: cd frontend; pnpm dev
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
