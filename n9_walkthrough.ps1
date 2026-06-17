$stageApi = "https://realtornet-staging.up.railway.app"
$script:propId = $null

function Auth-User($email, $password) {
    $resp = Invoke-RestMethod -Uri "${stageApi}/api/v1/auth/login" -Method Post -Body "username=$([System.Uri]::EscapeDataString($email))&password=$([System.Uri]::EscapeDataString($password))" -ContentType "application/x-www-form-urlencoded" -ErrorAction Stop
    return $resp.access_token
}

function Api-Post($url, $body, $token) {
    return Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json" -Headers @{ Authorization = "Bearer $token" } -ErrorAction Stop
}

function Api-Put($url, $body, $token) {
    return Invoke-RestMethod -Uri $url -Method Put -Body $body -ContentType "application/json" -Headers @{ Authorization = "Bearer $token" } -ErrorAction Stop
}

function Api-Patch($url, $body, $token) {
    if ($body) {
        return Invoke-RestMethod -Uri $url -Method Patch -Body $body -ContentType "application/json" -Headers @{ Authorization = "Bearer $token" } -ErrorAction Stop
    } else {
        return Invoke-RestMethod -Uri $url -Method Patch -Headers @{ Authorization = "Bearer $token" } -ErrorAction Stop
    }
}

function Api-Get($url, $token) {
    return Invoke-RestMethod -Uri $url -Method Get -Headers @{ Authorization = "Bearer $token" } -ErrorAction Stop
}

function Make-Json($body) {
    $json = ""
    $first = $true
    $json += "{"
    foreach ($key in $body.Keys) {
        if (-not $first) { $json += "," }
        $first = $false
        $val = $body[$key]
        if ($val -is [string]) { $json += "`"$key`":`"$val`"" }
        elseif ($val -is [int]) { $json += "`"$key`":$val" }
        elseif ($val -is [double]) { $json += "`"$key`":$val" }
        elseif ($val -eq $null) { $json += "`"$key`":null" }
        elseif ($val -is [bool]) { $json += "`"$key`":$($val.ToString().ToLower())" }
        else { $json += "`"$key`":`"$val`"" }
    }
    $json += "}"
    return $json
}

try {
    Write-Output "=== AUTHENTICATING ==="
    $script:agentToken = Auth-User "apineorbeenga@yahoo.com" "Markets26_"
    $script:ownerToken = Auth-User "apineorbeenga@outlook.com" "Markets26_"
    $script:adminToken = Auth-User "apineorbeenga@gmail.com" "Markets26_"
    $script:seekerToken = Auth-User "apineterngu19@gmail.com" "Markets26_"
    Write-Output "All 4 authenticated"

    Write-Output "`n=== STEP 1: Create Listing ==="
    $listingBody = Make-Json @{
        title = "N9 Mediation Lifecycle Test"
        description = "Integration test for Phase N"
        price = 350000
        property_type_id = 3
        bedroom_count = 3
        bathroom_count = 2
        square_feet = 1500
        address = "456 Test Ave"
        city = "Lagos"
        state = "Lagos"
        zip_code = "100001"
        country = "NG"
        latitude = 6.5244
        longitude = 3.3792
        listing_type = "sale"
        property_status = "available"
    }
    $listing = Api-Post "${stageApi}/api/v1/properties/" $listingBody $script:agentToken
    $script:propId = $listing.property_id
    Write-Output "Created: id=$($script:propId) status=$($listing.moderation_status)"

    $createdCheck = Api-Get "${stageApi}/api/v1/properties/$($script:propId)" $script:agentToken
    Write-Output "  has_instruction=$($createdCheck.has_instruction) instruction_text=$($createdCheck.instruction_text) latest_event_reason=$($createdCheck.latest_event_reason)"

    Write-Output "`n=== STEP 2: Submit for Review ==="
    $submitResult = Api-Patch "${stageApi}/api/v1/properties/$($script:propId)/submit-for-review" $null $script:agentToken
    Write-Output "Submitted: status=$($submitResult.moderation_status)"
    Write-Output "  has_instruction=$($submitResult.has_instruction)"

    Write-Output "`n=== STEP 3: Agency Owner Approves ==="
    $approveBody = Make-Json @{ moderation_reason = "Approved for admin review" }
    $approveResult = Api-Patch "${stageApi}/api/v1/properties/$($script:propId)/agency-approve" $approveBody $script:ownerToken
    Write-Output "Approved: status=$($approveResult.moderation_status)"

    Write-Output "`n=== STEP 4: Admin Verifies ==="
    $verifyResult = Api-Patch "${stageApi}/api/v1/properties/$($script:propId)/verify" "{}" $script:adminToken
    Write-Output "Live: status=$($verifyResult.moderation_status)"

    Write-Output "`n=== STEP 5: Admin Revokes ==="
    $revokeBody = Make-Json @{ moderation_reason = "Violates community guidelines - incorrect pricing" }
    $revokeResult = Api-Patch "${stageApi}/api/v1/properties/$($script:propId)/revoke" $revokeBody $script:adminToken
    Write-Output "Revoked: status=$($revokeResult.moderation_status) reason=$($revokeResult.latest_event_reason)"

    Write-Output "`n=== STEP 6: Agent Checks Revoked ==="
    $agentCheck = Api-Get "${stageApi}/api/v1/properties/$($script:propId)" $script:agentToken
    Write-Output "Agent view: status=$($agentCheck.moderation_status) has_instruction=$($agentCheck.has_instruction) latest_event_reason='$($agentCheck.latest_event_reason)'"

    Write-Output "  Checking edit gate (should fail without instruction)..."
    try {
        $editBody = Make-Json @{ price = 375000 }
        Api-Put "${stageApi}/api/v1/properties/$($script:propId)" $editBody $script:agentToken
        Write-Output "  Edit succeeded (unexpected)"
    } catch {
        Write-Output "  Edit blocked as expected"
    }

    Write-Output "`n=== STEP 7: Agency Owner Checks Revoked ==="
    $ownerCheck = Api-Get "${stageApi}/api/v1/properties/$($script:propId)" $script:ownerToken
    Write-Output "Owner view: has_instruction=$($ownerCheck.has_instruction) latest_event_reason='$($ownerCheck.latest_event_reason)'"

    Write-Output "`n=== STEP 8: Agency Owner Writes Instruction ==="
    $instructBody = Make-Json @{ instruction_text = "Please correct the pricing to market rate and resubmit" }
    $instructResult = Api-Patch "${stageApi}/api/v1/properties/$($script:propId)/instruct" $instructBody $script:ownerToken
    Write-Output "Instruction written: instruction_id=$($instructResult.instruction_id)"

    $afterInstruct = Api-Get "${stageApi}/api/v1/properties/$($script:propId)" $script:agentToken
    Write-Output "  has_instruction=$($afterInstruct.has_instruction) instruction_text='$($afterInstruct.instruction_text)'"

    Write-Output "`n=== STEP 9: Agent Edits Listing ==="
    $editBody = Make-Json @{ price = 375000; description = "Corrected pricing - N9 mediation test" }
    $editResult = Api-Put "${stageApi}/api/v1/properties/$($script:propId)" $editBody $script:agentToken
    Write-Output "Edited: status=$($editResult.moderation_status)"
    Write-Output "  (After edit, listing enters draft)"

    Write-Output "`n=== STEP 10: Full Resubmission Chain ==="
    
    $resubmit = Api-Patch "${stageApi}/api/v1/properties/$($script:propId)/submit-for-review" $null $script:agentToken
    Write-Output "  10a. Submitted: status=$($resubmit.moderation_status)"

    $reApprove = Api-Patch "${stageApi}/api/v1/properties/$($script:propId)/agency-approve" $approveBody $script:ownerToken
    Write-Output "  10b. Agency approved: status=$($reApprove.moderation_status)"

    $reVerify = Api-Patch "${stageApi}/api/v1/properties/$($script:propId)/verify" "{}" $script:adminToken
    Write-Output "  10c. Admin verified (live): status=$($reVerify.moderation_status)"
    Write-Output "      has_instruction=$($reVerify.has_instruction) instruction_text='$($reVerify.instruction_text)'"

    Write-Output "`n=== STEP 11: Admin Historical Views ==="
    $revHist = Api-Get "${stageApi}/api/v1/admin/properties/revocation-history?limit=5" $script:adminToken
    Write-Output "  Revocation history count: $($revHist.Count)"
    $rejHist = Api-Get "${stageApi}/api/v1/admin/properties/rejection-history?limit=5" $script:adminToken
    Write-Output "  Rejection history count: $($rejHist.Count)"
    Write-Output "  Historical views OK"

    Write-Output "`n=== STEP 12: listing_events Check ==="
    $events = Api-Get "${stageApi}/api/v1/properties/$($script:propId)/events" $script:agentToken
    Write-Output "  listing_events count: $($events.Count)"
    $events | ForEach-Object { Write-Output "    event_id=$($_.event_id) from=$($_.from_status) to=$($_.to_status) created=$($_.created_at)" }
    Write-Output "  listing_events OK"

    Write-Output "`n============================================"
    Write-Output "N.9 MEDIATION LIFECYCLE WALKTHROUGH COMPLETE"
    Write-Output "============================================"

} catch {
    Write-Output "ERROR at PID=$($script:propId): $($_.Exception.Message)"
    exit 1
}
