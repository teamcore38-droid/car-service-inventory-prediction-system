$ErrorActionPreference='Stop'
$recordPath=Join-Path $PSScriptRoot '.runtime/process.json'
if(-not(Test-Path -LiteralPath $recordPath)){Write-Host 'No owned system process recorded.';return}
$saved=Get-Content -LiteralPath $recordPath -Raw|ConvertFrom-Json
$running=Get-Process -Id $saved.id -ErrorAction SilentlyContinue
if($running -and $running.StartTime.ToUniversalTime() -eq ([datetime]$saved.started).ToUniversalTime()){
    & taskkill.exe /PID $saved.id /T /F | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Could not stop the recorded local process tree.'}
    Write-Host 'Stopped the integrated local system. Database files are preserved.'
}else{Write-Host 'The recorded process has already stopped.'}
Remove-Item -LiteralPath $recordPath
