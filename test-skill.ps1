# 测试OpenClaw WeChat MP技能包
Write-Host "=== OpenClaw WeChat MP Skill Package Test ===" -ForegroundColor Green

# 1. 检查必要文件是否存在
$requiredFiles = @("skill.json", "README.md", "install.ps1")
$yourMcpPath = "your-mcp-skill"
$requiredMcpFiles = @("SKILL.md", "package.json", "pyproject.toml")

Write-Host "`n1. 检查根目录文件:" -ForegroundColor Yellow
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "   ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "   ✗ $file (缺失)" -ForegroundColor Red
    }
}

Write-Host "`n2. 检查MCP服务目录文件:" -ForegroundColor Yellow
foreach ($file in $requiredMcpFiles) {
    $fullPath = Join-Path $yourMcpPath $file
    if (Test-Path $fullPath) {
        Write-Host "   ✓ $fullPath" -ForegroundColor Green
    } else {
        Write-Host "   ✗ $fullPath (缺失)" -ForegroundColor Red
    }
}

# 3. 验证skill.json格式
Write-Host "`n3. 验证skill.json格式:" -ForegroundColor Yellow
try {
    $skillJson = Get-Content "skill.json" | ConvertFrom-Json
    Write-Host "   ✓ skill.json 格式正确" -ForegroundColor Green
    Write-Host "   名称: $($skillJson.name)" -ForegroundColor Cyan
    Write-Host "   版本: $($skillJson.version)" -ForegroundColor Cyan
    Write-Host "   类型: $($skillJson.type)" -ForegroundColor Cyan
} catch {
    Write-Host "   ✗ skill.json 格式错误: $_" -ForegroundColor Red
}

# 4. 检查Python环境
Write-Host "`n4. 检查Python环境:" -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "   ✓ Python版本: $pythonVersion" -ForegroundColor Green
    
    # 检查pip
    $pipVersion = pip --version 2>&1
    Write-Host "   ✓ pip可用" -ForegroundColor Green
} catch {
    Write-Host "   ⚠ Python环境可能未正确配置" -ForegroundColor Yellow
    Write-Host "     请确保已安装Python 3.11+和pip" -ForegroundColor Yellow
}

Write-Host "`n=== 测试完成 ===" -ForegroundColor Green
Write-Host "`n下一步操作:" -ForegroundColor Yellow
Write-Host "1. 运行 install.ps1 安装依赖" -ForegroundColor Cyan
Write-Host "2. 将此目录复制到OpenClaw技能目录或发布到技能市场" -ForegroundColor Cyan
Write-Host "3. 在OpenClaw中使用 openclaw skills install <path> 安装" -ForegroundColor Cyan