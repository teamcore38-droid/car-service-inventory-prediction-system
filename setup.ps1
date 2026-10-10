param()
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
if(-not(Get-Command node -ErrorAction SilentlyContinue)){throw 'Install Node.js 22 LTS or newer first.'}
$pythonPath=Join-Path $projectRoot 'inventory-ml/.venv/Scripts/python.exe'
if(-not(Test-Path -LiteralPath $pythonPath)){
    $pythonLauncher=Get-Command py -ErrorAction SilentlyContinue
    if($pythonLauncher){& $pythonLauncher.Source -3.12 -m venv (Join-Path $projectRoot 'inventory-ml/.venv')}
    else {
        $workspacePython=Join-Path (Split-Path (Split-Path $projectRoot -Parent) -Parent) 'Inventory-Prediction/.venv/Scripts/python.exe'
        if(-not(Test-Path -LiteralPath $workspacePython)){throw 'Install Python 3.12 (with the py launcher), then run setup again.'}
        & $workspacePython -m venv (Join-Path $projectRoot 'inventory-ml/.venv')
    }
    if($LASTEXITCODE -ne 0){throw 'Python environment creation failed.'}
}
& $pythonPath -m pip install -r (Join-Path $projectRoot 'inventory-ml/requirements.txt')
if($LASTEXITCODE -ne 0){throw 'Python dependency installation failed.'}
$env:MONGOMS_DISABLE_POSTINSTALL='1'
foreach($folder in @('backend','admin-web')){
    Push-Location (Join-Path $projectRoot $folder)
    try {& npm.cmd ci --no-audit --no-fund;if($LASTEXITCODE -ne 0){throw "Dependency installation failed: $folder"}}
    finally{Pop-Location}
}
Write-Host 'Setup complete. Use Start-System.cmd.'
