# OpenClaw WeChat MP Skill - Installation Script
# This script installs the required dependencies for the WeChat MP MCP skill

Write-Host "Installing OpenClaw WeChat MP Skill dependencies..."

# Navigate to the mcp-server directory
Set-Location -Path "$PSScriptRoot\your-mcp-skill\mcp-server"

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

Write-Host "Installation completed successfully!"
Write-Host "The skill is ready to use with OpenClaw."