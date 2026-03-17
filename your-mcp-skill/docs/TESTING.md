# 本地测试指南

本文说明如何在本机测试本 MCP 服务，包括：

- 使用 MCP Inspector（带可视化界面）调用 Tools
- 无界面方式运行单元测试
- 常见问题排查（Windows/PowerShell）

## 前置条件

- Windows
- Python 3.11+
- Node.js（用于运行 MCP Inspector）

## 1. 安装依赖

在工程目录 `your-mcp-skill/mcp-server/` 下执行：

```powershell
cd f:\mcpServe\your-mcp-skill\mcp-server
python -m pip install -r requirements.txt
python -m playwright install chromium
```

如果 `playwright install chromium` 因网络原因无法下载浏览器（例如报 Executable doesn't exist），可以先跳过下载：

- 本项目默认开启系统浏览器回退（Windows 通常可用 Edge）
- 或在 `config/default.json` 里显式指定 `browser.channel` 为 `msedge` / `chrome`

如需跑测试（pytest）：

```powershell
python -m pip install pytest pytest-asyncio
```

## 2. 使用 MCP Inspector（推荐，可视化）

MCP Inspector 是一个可视化调试工具：启动后会提供一个浏览器 UI 用来连接 MCP server、查看 tools、发起调用并查看通知消息（包括服务端推送的 log/progress）。

### 2.1 启动 Inspector（STDIO 方式）

在 `your-mcp-skill/mcp-server/` 下执行：

```powershell
cd f:\mcpServe\your-mcp-skill\mcp-server
npx -y @modelcontextprotocol/inspector --transport stdio -- python -m openclaw_wechat_mcp
```

也可以在工程根目录 `your-mcp-skill/` 直接用 npm 脚本启动：

```powershell
cd f:\mcpServe\your-mcp-skill
npm run inspector
```

启动后在浏览器打开：

- http://127.0.0.1:6274

说明：

- 使用 STDIO 连接时，不需要你手动先启动 MCP server，Inspector 会拉起 `python -m openclaw_wechat_mcp`

### 2.2 在 Inspector 里验证工具是否可用

进入 UI 后：

1. 打开 Tools 列表，应该能看到：
   - `open_login_page`
   - `monitor_login`
   - `get_login_status`
   - `reset_login_state`
   - `publish_draft_from_draftbox`
2. 点击某个 tool，填入参数并执行，查看返回结果是否正常

### 2.3 测试扫码登录与“推消息”

目标：验证服务端可以返回二维码（base64），并持续监控页面状态，把阶段变化推送出来。

建议流程：

1. 先执行 `reset_login_state`，确保是“未登录状态”
2. 执行 `open_login_page`
   - 期待：返回 `qr.base64` / `qr.data_url` / `qr.selector` / `qr.source_url` 等字段与 `profile_dir`
3. 执行 `monitor_login`
   - 推荐参数：
     - `timeout_ms`: 120000
     - `poll_ms`: 1000
     - `push_qr_on_change`: true
   - 期待：在 UI 的日志/通知区域看到阶段变化的推送（例如 `await_scan` → `scanned_pending_confirm` → `logged_in`）
4. 用手机微信扫码并确认
   - 期待：`monitor_login` 最终返回 `logged_in: true`
5. 再执行 `get_login_status`
   - 期待：`logged_in: true`

提示：

- `monitor_login` 会在阶段变化时发送通知消息（log/progress）。Inspector UI 会展示这些消息，便于确认“推消息”链路正常。

## 3. 无界面测试（pytest）

在工程目录 `your-mcp-skill/` 下执行：

```powershell
cd f:\mcpServe\your-mcp-skill
python -m pytest -q
```

这些测试主要覆盖：

- 配置加载
- 步骤执行器（workflow）的行为
- 登录阶段检测（不依赖真实网页，使用 fake page）

## 4. 可视化调试浏览器（有头模式）

如果你希望看到真实浏览器窗口以便排查选择器/页面状态：

方式 A（推荐，按调用参数临时开启）：

在 Inspector 调用 `open_login_page` / `monitor_login` 时传入：

- `headless: false`
- `slow_mo_ms: 200`（可选，让点击更“慢”更容易观察）

方式 B（改配置，全局生效）：

1. 打开 `config/default.json`
2. 将 `browser.headless` 设置为 `false`
3. 重新启动 Inspector 再调用工具

## 5. 常见问题（Windows/PowerShell）

### 5.1 PowerShell 报 PSReadLine 异常

现象：运行 `npx ... inspector ...` 时提示 PSReadLine 的渲染异常（常见于某些集成终端环境）。

处理方式（二选一）：

1. 使用系统自带的 Windows Terminal / cmd 运行 Inspector 命令
2. 用无 profile 的 PowerShell 启动：

```powershell
powershell -NoProfile -Command "cd f:\mcpServe\your-mcp-skill\mcp-server; npx -y @modelcontextprotocol/inspector --transport stdio -- python -m openclaw_wechat_mcp"
```

### 5.2 二维码找不到

现象：`open_login_page` 返回 `qr: null` 或报“二维码提取失败”。

处理：

- 打开网页后，用浏览器开发者工具确认二维码元素的 CSS 选择器
- 将对应 selector 加入 `config/default.json` 的 `wechat_mp.qr_selectors`（按顺序尝试）
