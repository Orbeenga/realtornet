$stageApi = "https://realtornet-staging.up.railway.app"

$resp = Invoke-RestMethod -Uri "${stageApi}/api/v1/auth/login" -Method Post -Body "username=apineorbeenga@gmail.com&password=Markets26_" -ContentType "application/x-www-form-urlencoded" -ErrorAction Stop
$token = $resp.access_token

$ids = @(14, 23, 24, 25, 26)
foreach ($id in $ids) {
    try {
        $null = Invoke-RestMethod -Uri "${stageApi}/api/v1/admin/properties/${id}" -Method Delete -Headers @{ Authorization = "Bearer $token" } -ErrorAction Stop
        Write-Output "Deleted $id : OK"
    } catch {
        Write-Output "Delete $id : $($_.Exception.Message)"
    }
}
