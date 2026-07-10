# Start the FinAlly container (Windows PowerShell).
# Usage: .\scripts\start_windows.ps1 [-Build]
param([switch]$Build)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$image = "finally"
$name = "finally"

$exists = docker images -q $image
if ($Build -or -not $exists) {
    Write-Host "Building image '$image'..."
    docker build -t $image $Root
}

# Remove any existing container so this script is idempotent
docker rm -f $name 2>$null | Out-Null

if (-not (Test-Path "$Root/.env")) {
    Write-Warning ".env not found. Copy .env.example to .env and add your OPENROUTER_API_KEY."
}

Write-Host "Starting container '$name'..."
docker run -d --name $name `
    -v "${Root}/db:/app/db" `
    -p 8000:8000 `
    --env-file "$Root/.env" `
    $image

Write-Host "Open http://localhost:8000 in your browser"
