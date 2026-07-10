# Stop and remove the FinAlly container (Windows PowerShell).
# The db/ bind mount is untouched, so data persists.
$ErrorActionPreference = "Stop"

docker rm -f finally 2>$null | Out-Null
Write-Host "Stopped and removed container 'finally' (data in db/ preserved)."
