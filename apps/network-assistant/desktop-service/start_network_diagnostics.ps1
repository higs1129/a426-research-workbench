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
$pidFile = Join-Path $logRoot "server.pid"

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
    if ($health.ok) {
        Write-Host "Network diagnostics is already running on port $Port."
        exit 0
    }
} catch {
    # No healthy instance is listening yet.
}

$arguments = @(
    "-u",
    $serverScript,
    "--host", "127.0.0.1",
    "--port", $Port,
    "--peer", $Peer,
    "--ping-attempts", "6"
)
$process = Start-Process -FilePath $python.Source -ArgumentList $arguments -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
$process.Id | Set-Content -LiteralPath $pidFile -Encoding ascii

$deadline = (Get-Date).AddSeconds(12)
do {
    Start-Sleep -Milliseconds 300
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        if ($health.ok) {
            Write-Host "Network diagnostics started (PID $($process.Id))."
            Write-Host "Local:   http://127.0.0.1:$Port/"
            Write-Host "Tailnet: https://a426.tailabd98b.ts.net/netcheck/"
            exit 0
        }
    } catch {
        # Keep waiting until the deadline.
    }
} while ((Get-Date) -lt $deadline)

throw "Server did not become healthy. Check $stderrLog"
