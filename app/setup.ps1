param([string]$Python = '')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONUTF8='1'
if (!(Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if (!$Python) {
        $bundle = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        if (Test-Path -LiteralPath $bundle) { $Python=$bundle }
        else { $Python='python' }
    }
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required; pass -Python with its executable path.' }
}
& .venv\Scripts\python.exe -m pip install --cache-dir .pip-cache -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
Push-Location frontend
try {
    & npm.cmd ci --cache ..\.npm-cache --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'Ready. Double-click start.cmd; stop with stop.cmd.'
