param([ValidateSet('InstallCPU','PrepareOffline','InstallOffline','PreparePython')][string]$Action='InstallCPU')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$offlineProfilePath=Join-Path $projectRoot 'samstudio\resources\offline_profile.json'
if ($Action -eq 'InstallCPU' -and (Test-Path -LiteralPath $offlineProfilePath)) { $Action='InstallOffline' }
$offline=($Action -eq 'InstallOffline')
function Test-Python312([string]$candidate) {
    if (-not $candidate) { return $false }
    try { & $candidate -c 'import sys,struct; assert sys.version_info[:2]==(3,12) and struct.calcsize("P")==8' 2>$null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}
$pythonPath=Join-Path $projectRoot '.python312\python.exe'
if (-not (Test-Python312 $pythonPath)) {
    $pythonPath=$null
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try { $candidate=(& py -3.12 -c 'import sys; print(sys.executable)' 2>$null | Select-Object -Last 1); if ($LASTEXITCODE -eq 0 -and (Test-Python312 $candidate)) { $pythonPath=$candidate } } catch {}
    }
    if (-not $pythonPath -and (Get-Command python -ErrorAction SilentlyContinue)) {
        $candidate=(Get-Command python).Source
        if (Test-Python312 $candidate) { $pythonPath=$candidate }
    }
}
if (-not $pythonPath) {
    $spec=(Get-Content -LiteralPath (Join-Path $projectRoot 'packaging\python-runtimes.json') -Raw | ConvertFrom-Json).'windows-x86_64'
    $cacheFolder=if ($Action -in @('PrepareOffline','InstallOffline')) { 'offline-cache\runtime' } else { '.install-cache\runtime' }
    $cache=Join-Path $projectRoot $cacheFolder
    New-Item -ItemType Directory -Force -Path $cache | Out-Null
    $archive=Join-Path $cache $spec.filename
    if (-not (Test-Path -LiteralPath $archive)) {
        if ($offline) { throw 'Python runtime is missing from the offline cache. Run Prepare Offline on an online computer first.' }
        Write-Host 'Preparing verified project-local Python 3.12. Other Python installations remain unchanged.'
        [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $spec.url -OutFile ($archive+'.part') -UseBasicParsing
        Move-Item -LiteralPath ($archive+'.part') -Destination $archive
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $spec.sha256) { throw 'Python runtime SHA-256 check failed. The cached archive was not used.' }
    $destination=Join-Path $projectRoot '.python312'
    if (Test-Path -LiteralPath $destination) { throw 'Preserve or rename the existing invalid .python312 folder before retrying.' }
    $stage=Join-Path $projectRoot ('.python-stage-'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($archive,$stage)
        Move-Item -LiteralPath (Join-Path $stage 'tools') -Destination $destination
    } finally { Remove-Item -LiteralPath $stage -Recurse -Force }
    Set-Content -LiteralPath (Join-Path $destination '.samstudio-owned') -Value 'Project-local Python 3.12'
    $pythonPath=Join-Path $destination 'python.exe'
    if (-not (Test-Python312 $pythonPath)) { throw 'Prepared Python version/architecture check failed.' }
}
switch ($Action) {
    'PreparePython' { Write-Host ('Python 3.12 ready: '+$pythonPath); exit 0 }
    'InstallCPU' { & $pythonPath (Join-Path $projectRoot 'scripts\install_environment.py') --backend cpu }
    'PrepareOffline' { & $pythonPath (Join-Path $projectRoot 'scripts\prepare_offline.py') }
    'InstallOffline' { & $pythonPath (Join-Path $projectRoot 'scripts\install_offline.py') }
}
exit $LASTEXITCODE
