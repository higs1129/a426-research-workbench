param(
    [string]$File,
    [string]$Python,
    [switch]$Check
)
$ErrorActionPreference = 'Stop'
$appPath = Join-Path $PSScriptRoot 'viewer.py'
$candidates = @()
$explicitPython = $false
if ($Python) {
    $candidates = @($Python)
    $explicitPython = $true
} elseif ($env:ARRAY_VIEWER_PYTHON) {
    $candidates = @($env:ARRAY_VIEWER_PYTHON)
    $explicitPython = $true
} else {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike '*\WindowsApps\*') {
        $candidates += $pythonCommand.Source
    }
    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyCommand) {
        $resolvedPython = & $pyCommand.Source -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolvedPython) { $candidates += [string]$resolvedPython }
    }
    # Optional discovery of an existing runtime, never installed or copied here.
    $codexPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $codexPython -PathType Leaf) { $candidates += $codexPython }
}
$selectedPython = $null
foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
    try {
        & $candidate -B -c 'import sys; assert sys.version_info >= (3, 10); import numpy, tkinter; from PIL import Image, ImageTk; assert Image.Resampling' 2>$null
        if ($LASTEXITCODE -eq 0) { $selectedPython = $candidate; break }
    } catch {
        # Try another existing interpreter only when none was explicitly chosen.
        if ($explicitPython) { break }
    }
}
if (-not $selectedPython) {
    Write-Host 'No usable Python found. Requires Python 3.10+, NumPy, Pillow and tkinter.' -ForegroundColor Red
    Write-Host 'Use: .\start_viewer.ps1 -Python "C:\path\to\python.exe" [-File "D:\data\sample.npz"]'
    Write-Host 'Or set ARRAY_VIEWER_PYTHON to the full interpreter path. See README.md.'
    exit 1
}
$viewerArgs = @('-B', $appPath)
if ($Check) { $viewerArgs += '--check' }
if ($File) { $viewerArgs += $File }
& $selectedPython @viewerArgs
exit $LASTEXITCODE
