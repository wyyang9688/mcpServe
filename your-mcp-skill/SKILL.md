---
name: "openclaw-wechat-mp-mcp"
description: "通过 MCP 控制浏览器完成微信公众号登录与页面流程自动化。Invoke when 需要扫码登录、保存登录态或按步骤点击/等待页面状态。"
version: "0.1.0"
runtime: "python"
entry:
  cwd: "mcp-server"
  command: "python"
  args: ["-m", "openclaw_wechat_mcp"]
config:
  default: "config/default.json"
---

# OpenClaw WeChat MP MCP

本工程提供一个基于 MCP 的浏览器自动化服务：

- 打开可配置的登录页并提取二维码图片（base64），用于扫码登录
- 保存/复用登录状态
- 按步骤执行页面操作（点击、等待、判断状态），并把执行结果回传给大模型

## 工程结构

```
your-mcp-skill/
├── SKILL.md
├── config/
│   └── default.json
├── mcp-server/
│   ├── pyproject.toml
│   └── src/openclaw_wechat_mcp/
├── docs/
├── examples/
└── tests/
```

## 快速开始

1. 安装依赖（含 Playwright）
2. 安装浏览器内核：`playwright install chromium`
3. 启动 MCP Server：在 `mcp-server/` 下执行 `python -m openclaw_wechat_mcp`

## 工具一览

- `open_login_page`: 打开登录页并返回二维码 base64
- `wait_for_login`: 等待扫码登录成功（轮询检测）
- `monitor_login`: 监控扫码/过期/登录阶段并推送消息
- `get_login_status`: 返回当前是否已登录
- `reset_login_state`: 清理登录态并重新登录
- `publish_draft_from_draftbox`: 按步骤执行点击/等待等操作，返回每步结果与整体完成状态
- `wait_for_publish_success`: 等待发布完成（监控重定向到首页与“近期发表”区域）

## OpenClaw 推荐编排

MCP 的服务端通知（右侧日志/notifications）是否会进入大模型上下文，取决于具体 MCP 客户端。为了让大模型稳定拿到“是否登录成功”的结论，推荐以 tools/call 的返回值为准，并按下面的顺序做条件编排。

### 登录流程（稳定版）

1. 调用 `open_login_page`
   - 如果返回 `logged_in=true`：说明当前会话已登录（可能已重定向到 `https://mp.weixin.qq.com/cgi-bin/home`），直接进入后续业务流程
   - 如果返回 `logged_in=false`：
     - 使用 `qr.data_url`（优先）或 `qr.base64` 展示二维码，让用户用手机微信扫码并确认
2. 立刻调用 `monitor_login`
   - `monitor_login` 会持续监控，直到登录成功或超时
   - 当返回 `logged_in=true` 时，再进入后续业务流程（例如进入草稿箱、发布文章等）
3. 失败处理
   - 若 `monitor_login` 超时（`logged_in=false`），提示用户重试
   - 如果用户需要强制重新扫码，先调用 `reset_login_state` 清理 profile 后再重走登录流程

### 发布确认（稳定版）

当发布流程触发“微信验证”时，`publish_draft_from_draftbox` 会返回 `requires_user_action=true` 且携带二维码（`qr.data_url/base64`）。用户/管理员完成扫码验证后，页面通常会重定向到公众号平台首页：

- `https://mp.weixin.qq.com/cgi-bin/home`

这时推荐由大模型调用 `wait_for_publish_success` 做最终确认，再向用户提示“发表成功”。该工具会轮询当前浏览器页 URL 是否进入首页，并尝试检测首页的“近期发表”区域（可选匹配标题）。

### 示例（伪代码）

```text
resp = open_login_page(...)
if resp.logged_in:
  continue_business()
else:
  show_qr(resp.qr.data_url or resp.qr.base64)
  login = monitor_login(timeout_ms=..., poll_ms=...)
  if login.logged_in:
    continue_business()
  else:
    ask_user_retry_or_reset()
```

### 常用调试参数（可视化浏览器）

在 `open_login_page` / `monitor_login` 调用时可传：

- `headless=false`：打开真实浏览器窗口
- `slow_mo_ms=200`：放慢点击/跳转，便于观察
- `channel="msedge"`：使用系统 Edge（可避免 Playwright 浏览器下载失败）
