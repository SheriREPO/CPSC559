while ($true) {
    foreach ($i in 1..5) {
        docker cp server_$i`:/app/data/tasks.db ./server${i}_tasks.db
    }
    Write-Host "All DBs refreshed at $(Get-Date -Format 'HH:mm:ss')"
    Start-Sleep -Seconds 5
}