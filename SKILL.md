---
name: "openclaw-wechat-mp"
description: "通过 MCP 控制浏览器完成微信公众号登录与页面流程自动化。Invoke when 需要扫码登录、保存登录态或按步骤点击/等待页面状态。"
version: "0.1.0"
type: "mcp"
---

# OpenClaw WeChat MP Skill

本技能提供微信公众号自动化功能，包括扫码登录、草稿箱管理和文章发布。

## 安装后自动配置

安装此技能后，OpenClaw会：
- 自动启动MCP服务
- 自动配置连接
- 提供以下工具调用：
  - `open_login_page`: 打开登录页并返回二维码
  - `monitor_login`: 监控登录状态  
  - `publish_draft_from_draftbox`: 发布草稿箱文章
  - `wait_for_publish_success`: 确认发布成功
  - `reset_login_state`: 重置登录状态
  - `get_login_status`: 获取当前登录状态
  - `wait_for_login`: 等待登录完成

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

## 使用方法

安装后直接调用工具即可，无需手动配置MCP连接。

### 登录流程（稳定版）

1. 调用 `open_login_page`
   - 如果返回 `logged_in=true`：说明当前会话已登录，直接进入后续业务流程
   - 如果返回 `logged_in=false`：
     - 使用 `qr.data_url`（优先）或 `qr.base64` 展示二维码，让用户用手机微信扫码并确认
2. 立刻调用 `monitor_login`
   - `monitor_login` 会持续监控，直到登录成功或超时
   - 当返回 `logged_in=true` 时，再进入后续业务流程
3. 失败处理
   - 若 `monitor_login` 超时（`logged_in=false`），提示用户重试
   - 如果用户需要强制重新扫码，先调用 `reset_login_state` 清理 profile 后再重走登录流程

### 发布确认（稳定版）

当发布流程触发"微信验证"时，`publish_draft_from_draftbox` 会返回 `requires_user_action=true` 且携带二维码。用户完成扫码验证后，推荐调用 `wait_for_publish_success` 做最终确认。

## 技术栈

- **运行时**: Python >= 3.11
- **协议**: Model Context Protocol (MCP)
- **浏览器自动化**: Playwright
- **传输方式**: stdio

## 调试参数

在工具调用时可传：
- `headless=false`：打开真实浏览器窗口
- `slow_mo_ms=200`：放慢点击/跳转，便于观察
- `channel="msedge"`：使用系统 Edge 浏览器