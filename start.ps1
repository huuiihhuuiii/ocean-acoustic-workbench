param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
$url = 'http://127.0.0.1:8765'
$running = $false
try { $health = Invoke-RestMethod "$url/api/health" -TimeoutSec 2; $running = $health.version -in @('0.2.0','0.4.0','0.5.0','0.7.0') } catch {}
if (-not $running) {
    $runtimeFile = Join-Path $appRoot '.local/runtime.json'
    $venvPython = Join-Path $appRoot '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $venvPython) { $pythonExe = $venvPython }
    elseif (Test-Path -LiteralPath $runtimeFile) {
        $runtime = Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json
        $pythonExe = $runtime.python
        $env:PYTHONPATH = $runtime.pythonpath
    } else { throw 'Python environment missing. See README.md.' }
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Configured Python executable not found.' }
    $env:PYTHONIOENCODING = 'utf-8'
    $entry = Join-Path $appRoot 'backend/app.py'
    $process = Start-Process -FilePath $pythonExe -ArgumentList @('"' + $entry + '"') -WorkingDirectory $appRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $appRoot '.local/server.stdout.log') -RedirectStandardError (Join-Path $appRoot '.local/server.stderr.log')
    $process.Id | Set-Content (Join-Path $appRoot '.local/server.pid')
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        try { $health = Invoke-RestMethod "$url/api/health" -TimeoutSec 1; $running = $health.version -in @('0.2.0','0.4.0','0.5.0','0.7.0'); if ($running) { break } } catch {}
        if ($process.HasExited) { throw 'Server exited. Check .local/server.stderr.log.' }
    }
    if (-not $running) { throw 'Server startup timed out. Check .local/server.stderr.log.' }
}
Write-Host "Ocean Acoustics Workbench: $url"
if (-not $NoBrowser) { Start-Process $url }
