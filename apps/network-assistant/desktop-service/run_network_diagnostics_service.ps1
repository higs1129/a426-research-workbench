[CmdletBinding()]
param(
    [int]$Port = 8788,
    [string]$Peer = "V2359A"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverScript = Join-Path $scriptRoot "server.py"
$python = Get-Command python -ErrorAction Stop
$logRoot = Join-Path $env:TEMP "a426-network-diagnostics"
$stdoutLog = Join-Path $logRoot "server.stdout.log"
$stderrLog = Join-Path $logRoot "server.stderr.log"

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

while ($true) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        if ($health.ok) {
            Start-Sleep -Seconds 20
            continue
        }
    } catch {
        # The local service is absent or unhealthy; launch it below.
    }

    Add-Content -LiteralPath $stdoutLog -Encoding UTF8 `
        -Value "[$(Get-Date -Format o)] starting network diagnostics service"
    try {
        & $python.Source -u $serverScript `
            --host 127.0.0.1 `
            --port $Port `
            --peer $Peer `
            --ping-attempts 6 `
            1>> $stdoutLog 2>> $stderrLog
        $exitCode = $LASTEXITCODE
    } catch {
        $exitCode = 1
        Add-Content -LiteralPath $stderrLog -Encoding UTF8 `
            -Value "[$(Get-Date -Format o)] launcher error: $($_.Exception.Message)"
    }

    Add-Content -LiteralPath $stderrLog -Encoding UTF8 `
        -Value "[$(Get-Date -Format o)] server exited with code $exitCode; retrying in 5 seconds"
    Start-Sleep -Seconds 5
}
