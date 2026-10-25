$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = '1'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Run setup.ps1 first to install the locked dependencies.' }
if (!(Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Frontend build missing. Run setup.ps1.' }
$dataFolder = Join-Path $PSScriptRoot 'data'
New-Item -ItemType Directory -Force -Path $dataFolder | Out-Null
$pidFile = Join-Path $dataFolder 'server.pid'
if (Test-Path -LiteralPath $pidFile) {
    $existingId = [int](Get-Content -LiteralPath $pidFile)
    $existing = Get-Process -Id $existingId -ErrorAction SilentlyContinue
    if ($existing) { Write-Host 'The server is already running at http://127.0.0.1:8765'; exit 0 }
}
$process = Start-Process -FilePath $python -ArgumentList '-X utf8 -m uvicorn backend.main:app --host 127.0.0.1 --port 8765' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $dataFolder 'server.log') -RedirectStandardError (Join-Path $dataFolder 'server-error.log') -PassThru
$process.Id | Set-Content -LiteralPath $pidFile
Write-Host 'CS2 Demo Lab: http://127.0.0.1:8765'
Write-Host 'Stop with stop.ps1. Runtime does not need Internet.'
