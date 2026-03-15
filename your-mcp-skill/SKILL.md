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
- `run_web_steps`: 按步骤执行点击/等待等操作，返回每步结果与整体完成状态
