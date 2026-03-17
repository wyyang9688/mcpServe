# OpenClaw WeChat MP Skill - Windows Installation Script

Write-Host "Installing OpenClaw WeChat MP Skill dependencies..." -ForegroundColor Green

# Navigate to the MCP server directory
Set-Location -Path "$PSScriptRoot\your-mcp-skill\mcp-server"

# Install Python dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: pip install failed. Please ensure Python >= 3.11 and pip are installed." -ForegroundColor Red
}

# Install Playwright browsers
Write-Host "Installing Playwright browsers..." -ForegroundColor Yellow
python -m playwright install chromium

if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Playwright browser installation failed. You may need to run this as administrator." -ForegroundColor Red
}

# Create data directory if it doesn't exist
$dataDir = "$PSScriptRoot\your-mcp-skill\mcp-server\data"
if (!(Test-Path -Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}

Write-Host "OpenClaw WeChat MP Skill installation completed!" -ForegroundColor Green
Write-Host "The skill will automatically start when used in OpenClaw." -ForegroundColor Cyan