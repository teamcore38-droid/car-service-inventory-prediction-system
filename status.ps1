foreach($service in @(@{Name='Dashboard';Url='http://127.0.0.1:5180'},@{Name='API';Url='http://127.0.0.1:5008/health'},@{Name='Model';Url='http://127.0.0.1:8770/health'})){
    try{$response=Invoke-WebRequest -UseBasicParsing $service.Url -TimeoutSec 3;Write-Host "$($service.Name): ready ($($response.StatusCode))"}catch{Write-Host "$($service.Name): not ready"}
}
Write-Host 'Logs: .runtime/*.log'
