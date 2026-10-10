param([switch]$OpenBrowser)
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$runtimeRoot=Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$recordPath=Join-Path $runtimeRoot 'process.json'
if(Test-Path -LiteralPath $recordPath){
    $saved=Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    $running=Get-Process -Id $saved.id -ErrorAction SilentlyContinue
    if($running -and $running.StartTime.ToUniversalTime() -eq ([datetime]$saved.started).ToUniversalTime()){
        Write-Host 'System already running: http://127.0.0.1:5180'
        if($OpenBrowser){Start-Process 'http://127.0.0.1:5180' -WindowStyle Hidden};return
    }
}
$nodePath=(Get-Command node -ErrorAction Stop).Source
$pythonPaths=@((Join-Path $projectRoot 'inventory-ml/.venv/Scripts/python.exe'),(Join-Path (Split-Path (Split-Path $projectRoot -Parent) -Parent) 'Inventory-Prediction/.venv/Scripts/python.exe'))
$pythonPath=$pythonPaths | Where-Object{Test-Path -LiteralPath $_} | Select-Object -First 1
if(-not $pythonPath -or -not(Test-Path -LiteralPath (Join-Path $projectRoot 'backend/node_modules/mongodb-memory-server')) -or -not(Test-Path -LiteralPath (Join-Path $projectRoot 'admin-web/node_modules/vite'))){& (Join-Path $projectRoot 'setup.ps1');$pythonPath=Join-Path $projectRoot 'inventory-ml/.venv/Scripts/python.exe'}
$env:INVENTORY_PYTHON=$pythonPath
$process=Start-Process -FilePath $nodePath -ArgumentList @('run-system.cjs') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'launcher.out.log') -RedirectStandardError (Join-Path $runtimeRoot 'launcher.err.log')
$record=[PSCustomObject]@{id=$process.Id;started=$process.StartTime.ToUniversalTime().ToString('o')}
$record|ConvertTo-Json|Set-Content -LiteralPath $recordPath
Write-Host 'Starting locally. First start on a new computer downloads MongoDB from its official distribution and can take several minutes.'
$deadline=(Get-Date).AddSeconds(40)
do {
    try {
        $health=Invoke-RestMethod 'http://127.0.0.1:5008/health' -TimeoutSec 2
        $model=Invoke-RestMethod 'http://127.0.0.1:8770/health' -TimeoutSec 2
        $web=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5180' -TimeoutSec 2
        if($health.status -eq 'OK' -and $model.service -eq 'inventory-daily' -and $web.StatusCode -eq 200){
            Write-Host 'Ready: http://127.0.0.1:5180'
            if($OpenBrowser){Start-Process 'http://127.0.0.1:5180' -WindowStyle Hidden};return
        }
    } catch {}
    if($process.HasExited){throw "Startup failed. See $runtimeRoot/launcher.err.log and service logs."}
    Start-Sleep -Milliseconds 400
}while((Get-Date)-lt $deadline)
Write-Host 'Services are still starting. Run Status-System.cmd to check progress. Logs are in .runtime.'
if($OpenBrowser){Start-Process 'http://127.0.0.1:5180' -WindowStyle Hidden}
