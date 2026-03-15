---
name: "openclaw-wechat-mp-mcp"
description: "生成/维护微信公众号网页自动化的 MCP 服务工程。Invoke when 需要搭建 MCP Server、添加扫码登录/登录态持久化/页面步骤执行能力或补齐 OpenClaw 打包结构。"
---

# OpenClaw WeChat MP MCP

## 目标

为 OpenClaw 打包安装提供一个 Python 版 MCP Server 工程骨架，并实现：

- 打开登录页并返回二维码 base64
- 保存登录态并检测是否已登录
- 按步骤执行页面操作（点击/等待/脚本）

## 约束

- 工程根目录包含 `SKILL.md`、`config/default.json`、`mcp-server/`、`docs/`、`examples/`、`tests/`
- 浏览器自动化优先使用 Playwright，并通过持久化 profile 保存登录状态

