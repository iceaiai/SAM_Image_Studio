param([ValidateSet('InstallCPU','PrepareOffline','InstallOffline','PreparePython')][string]$Action='InstallCPU')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$offlineProfilePath=Join-Path $projectRoot 'samstudio\resources\offline_profile.json'
if ($Action -eq 'InstallCPU' -and (Test-Path -LiteralPath $offlineProfilePath)) { $Action='InstallOffline' }
$offline=($Action -eq 'InstallOffline')
function Get-Python312Status([string]$candidate) {
    if (-not $candidate -or -not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        return @{ Ready = $false; Detail = "Python executable not found: $candidate" }
    }
    # Windows PowerShell 5.1 strips embedded double quotes from native arguments.
    # Use a quote-free probe and an explicit exit code, even with PYTHONOPTIMIZE set.
    $ErrorActionPreference = 'Continue'
    try {
        $result = & $candidate -I -c 'import sys; print(sys.version.split()[0], sys.maxsize.bit_length() + 1); sys.exit(0 if sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32 else 1)' 2>&1
        $exitCode = $LASTEXITCODE
        $output = ($result | Out-String).Trim()
        $ready = $exitCode -eq 0 -and $output -match '(?m)^3\.12\.\S+ 64\r?$'
        return @{ Ready = $ready; Detail = "Python at '$candidate' exited with code ${exitCode}. $output" }
    } catch {
        return @{ Ready = $false; Detail = "Could not start Python at '${candidate}': $($_.Exception.Message)" }
    }
}
$destination=Join-Path $projectRoot '.python312'
$localPython=Join-Path $destination 'python.exe'
$localStatus=Get-Python312Status $localPython
$pythonPath=$null
if ($localStatus.Ready) {
    $pythonPath=$localPython
} else {
    $launcher=Get-Command py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($launcher) {
        try {
            $candidate=(& $launcher.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null | Select-Object -Last 1)
            if ($LASTEXITCODE -eq 0 -and (Get-Python312Status $candidate).Ready) { $pythonPath=$candidate }
        } catch {}
    }
    if (-not $pythonPath) {
        $installed=Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($installed -and (Get-Python312Status $installed.Source).Ready) { $pythonPath=$installed.Source }
    }
}
if (-not $pythonPath) {
    if (Test-Path -LiteralPath $destination) {
        throw "Existing .python312 cannot run as 64-bit Python 3.12. $($localStatus.Detail) Preserve it by renaming the folder before retrying."
    }
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
    $stage=Join-Path $projectRoot ('.python-stage-'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($archive,$stage)
        $runtime=Join-Path $stage $spec.archive_root
        $preparedStatus=Get-Python312Status (Join-Path $runtime 'python.exe')
        if (-not $preparedStatus.Ready) {
            throw "Prepared Python failed the 64-bit Python 3.12 check. $($preparedStatus.Detail)"
        }
        Set-Content -LiteralPath (Join-Path $runtime '.samstudio-owned') -Value 'Project-local Python 3.12'
        # Move within the project only after validation. Directory.Move cannot
        # nest or overwrite this runtime if another installer got there first.
        [IO.Directory]::Move($runtime,$destination)
    } finally { Remove-Item -LiteralPath $stage -Recurse -Force }
    $pythonPath=$localPython
}
switch ($Action) {
    'PreparePython' { Write-Host ('Python 3.12 ready: '+$pythonPath); exit 0 }
    'InstallCPU' { & $pythonPath (Join-Path $projectRoot 'scripts\install_environment.py') --backend cpu }
    'PrepareOffline' { & $pythonPath (Join-Path $projectRoot 'scripts\prepare_offline.py') }
    'InstallOffline' { & $pythonPath (Join-Path $projectRoot 'scripts\install_offline.py') }
}
exit $LASTEXITCODE
