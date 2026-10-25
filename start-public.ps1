param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
& (Join-Path $appRoot 'start.ps1') -NoBrowser
$venvPython = Join-Path $appRoot '.venv/Scripts/python.exe'
if (Test-Path -LiteralPath $venvPython) { $pythonExe = $venvPython }
elseif (Test-Path -LiteralPath (Join-Path $appRoot '.local/runtime.json')) {
    $runtime = Get-Content (Join-Path $appRoot '.local/runtime.json') -Raw | ConvertFrom-Json
    $pythonExe = $runtime.python
    $env:PYTHONPATH = $runtime.pythonpath
} else { throw 'Python environment missing. Install backend/requirements.txt in .venv first.' }
$env:PYTHONIOENCODING = 'utf-8'
foreach ($name in @('gateway','bridge')) {
    $entry = if ($name -eq 'gateway') { 'public_gateway.py' } else { 'cloud_bridge.py' }
    $pidFile = Join-Path $appRoot ".local/$name.pid"
    $running = $false
    if (Test-Path -LiteralPath $pidFile) {
        $savedProcessId = [int](Get-Content -LiteralPath $pidFile)
        $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$savedProcessId" -ErrorAction SilentlyContinue
        $running = $existing -and $existing.CommandLine.Contains($entry) -and $existing.CommandLine.Contains($appRoot)
    }
    if (-not $running) {
        $process = Start-Process -FilePath $pythonExe -ArgumentList @('"' + (Join-Path $appRoot "backend/$entry") + '"') -WorkingDirectory $appRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $appRoot ".local/$name.stdout.log") -RedirectStandardError (Join-Path $appRoot ".local/$name.stderr.log")
        $process.Id | Set-Content -LiteralPath $pidFile
    }
}
$publicRuntime = Get-Content (Join-Path $appRoot '.local/public-runtime.json') -Raw | ConvertFrom-Json
Write-Host "Public site: $($publicRuntime.site_origin)"
if (-not $NoBrowser) { Start-Process $publicRuntime.site_origin }
