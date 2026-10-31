$ErrorActionPreference = 'Stop'
$configPath = Join-Path $PSScriptRoot 'config.json'
if (-not (Test-Path -LiteralPath $configPath)) { throw 'Copy config.example.json to config.json and configure it first.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$address = Get-NetIPAddress -InterfaceIndex $config.interface_index -AddressFamily IPv4 | Where-Object {$_.AddressState -eq 'Preferred' -and $_.IPAddress -eq $config.local_ip}
if (-not $address) { throw 'The configured physical NIC/address is unavailable. No proxy fallback is allowed.' }
$python = (Get-Command python -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) { throw 'Use a standard Windows Python installation with pythonw.exe.' }
$bridgePath = Join-Path $PSScriptRoot 'direct_bridge.py'
$bridge = Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'pythonw.exe' -and $_.CommandLine -and $_.CommandLine.Contains($bridgePath)}
if (-not $bridge) {
    Start-Process -FilePath $pythonw -ArgumentList ('"{0}"' -f $bridgePath) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
}
if (-not (Get-Process obs64 -ErrorAction SilentlyContinue)) {
    $obsArgs = '--profile "{0}" --collection "{1}"' -f $config.obs_profile, $config.obs_collection
    Start-Process -FilePath $config.obs_exe -WorkingDirectory (Split-Path $config.obs_exe) -ArgumentList $obsArgs
}
