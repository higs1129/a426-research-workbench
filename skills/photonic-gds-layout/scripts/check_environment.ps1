param(
    [string]$PythonExe = "python",
    [string]$KLayoutExe = ""
)

$ErrorActionPreference = "Stop"

function Resolve-KLayoutExecutable {
    param([string]$ExplicitPath)
    if ($ExplicitPath) {
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }
    $command = Get-Command klayout_app.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $uninstallRoots = @(
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    $entry = Get-ItemProperty $uninstallRoots -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match 'KLayout' } |
        Sort-Object DisplayVersion -Descending |
        Select-Object -First 1
    if ($entry -and $entry.UninstallString) {
        $installDir = Split-Path -Parent $entry.UninstallString.Trim('"')
        $candidate = Join-Path $installDir 'klayout_app.exe'
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw "KLayout executable was not found. Pass -KLayoutExe explicitly."
}

$resolvedKLayout = Resolve-KLayoutExecutable -ExplicitPath $KLayoutExe
$versionInfo = (Get-Item -LiteralPath $resolvedKLayout).VersionInfo
$pythonVersion = & $PythonExe --version 2>&1
$capabilitiesRaw = & $PythonExe -c "import importlib.util,json; print(json.dumps({n: bool(importlib.util.find_spec(n)) for n in ['klayout','klink','gdsfactory','yaml','matplotlib']}))"
$capabilities = $capabilitiesRaw | ConvertFrom-Json
$listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -eq 8082 -or ($_.LocalPort -ge 8765 -and $_.LocalPort -le 8799) } |
    Select-Object LocalAddress, LocalPort, OwningProcess

[pscustomobject]@{
    ok = $true
    python = $pythonVersion
    klayout_exe = $resolvedKLayout
    klayout_version = $versionInfo.ProductVersion
    capabilities = $capabilities
    listeners = @($listeners)
} | ConvertTo-Json -Depth 5
