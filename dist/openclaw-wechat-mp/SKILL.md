---
name: "openclaw-wechat-mp"
description: "通过 MCP 控制浏览器完成微信公众号登录与页面流程自动化"
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

## 使用方法

安装后直接调用工具即可，无需手动配置MCP连接。