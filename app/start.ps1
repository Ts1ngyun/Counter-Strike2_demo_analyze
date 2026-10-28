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
    if ($existing) {
        if ($existing.Path -ne $python) { throw 'PID belongs to another executable. Check app/data/server.pid.' }
        try { $health = Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 3 }
        catch { throw 'The existing server is not ready. Run STOP.cmd, then START.cmd.' }
        if (!$health.ok -or !$health.local_only) { throw 'Unexpected service on port 8765.' }
        Write-Host 'The server is already running at http://127.0.0.1:8765'; exit 0
    }
}
$process = Start-Process -FilePath $python -ArgumentList '-X utf8 -m uvicorn backend.main:app --host 127.0.0.1 --port 8765' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $dataFolder 'server.log') -RedirectStandardError (Join-Path $dataFolder 'server-error.log') -PassThru
$process.Id | Set-Content -LiteralPath $pidFile
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    $process.Refresh()
    if ($process.HasExited) { throw 'Server exited. See app/data/server-error.log.' }
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 1
        if ($health.ok -and $health.local_only) { $ready = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 500
}
if (!$ready) { throw 'Server startup timed out. See app/data/server-error.log or run STOP.cmd.' }
Write-Host 'CS2 Demo Lab: http://127.0.0.1:8765'
Write-Host 'Stop with stop.ps1. Runtime does not need Internet.'
