$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$pidFile = Join-Path $PSScriptRoot 'data\server.pid'
if (Test-Path -LiteralPath $pidFile) {
    $serverId = [int](Get-Content -LiteralPath $pidFile)
    $process = Get-Process -Id $serverId -ErrorAction SilentlyContinue
    $expectedPython = (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')
    if ($process) {
        if ($process.Path -ne $expectedPython) { throw 'PID belongs to another executable. Refusing to stop it.' }
        # Ask the local server to gracefully stop its workers, then exit.
        try { Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8765/api/shutdown' | Out-Null }
        catch { Write-Warning 'Server did not accept graceful shutdown. Use Task Manager for this PID if needed.'; throw }
    }
    Remove-Item -LiteralPath $pidFile
    Write-Host 'Stopped.'
}
