#!/usr/bin/env pwsh
<#
AMAZON SESSION BOOTSTRAP - Interactive Login Script
This script will:
1. Open a real browser window
2. Navigate to Amazon signin page
3. Wait for you to manually log in
4. Auto-detect when login is complete
5. Save your session for checkout automation
#>

Write-Host ""
Write-Host "========================================================================"
Write-Host "AMAZON BUYER SESSION BOOTSTRAP"
Write-Host "========================================================================"
Write-Host ""
Write-Host "A browser window will open. Follow these steps:"
Write-Host ""
Write-Host "1. Log into Amazon with your email and password"
Write-Host "2. Complete 2FA/OTP if Amazon prompts for it"
Write-Host "3. Wait for redirect to the Amazon homepage"
Write-Host "4. The script will auto-detect when you're logged in"
Write-Host ""
Write-Host "DO NOT:"
Write-Host "- Close the browser window"
Write-Host "- Log out"
Write-Host "- Clear cookies or site data"
Write-Host ""
Write-Host "The session will be saved to:"
Write-Host "  backend/credentials/amazon_buyer_session.json"
Write-Host ""
Write-Host "========================================================================"
Write-Host ""
Read-Host "Press Enter to start..."

cd "D:\Amazon-AI-Fulfillment-Agent\backend"
python -m jobs.bootstrap_amazon_session

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================================================"
    Write-Host "SUCCESS! Session saved."
    Write-Host "========================================================================"
    Write-Host ""
    Write-Host "You can now run the checkout demo:"
    Write-Host "  cd backend"
    Write-Host "  python -m jobs.demo_guest_checkout_fulfillment"
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "========================================================================"
    Write-Host "Bootstrap did not complete successfully."
    Write-Host "========================================================================"
    Write-Host ""
    Write-Host "Try again or check the browser window for any errors."
    Write-Host ""
}

Read-Host "Press Enter to close..."
