# OpenClaw WeChat MP MCP Skill

微信公众号自动化技能，通过MCP协议提供扫码登录、草稿箱管理和文章发布功能。

## 功能特性

- **扫码登录**：自动打开微信公众号登录页，提取二维码供用户扫码
- **登录状态管理**：自动检测和维护登录状态，支持会话持久化
- **草稿箱操作**：自动进入草稿箱，选择并发布指定文章
- **发布确认**：监控发布过程，确认文章成功发布
- **微信验证处理**：自动处理发布时的微信扫码验证

## 安装要求

- Python >= 3.11
- Playwright >= 1.42.0
- Windows/Linux/macOS系统

## 使用方法

安装此技能后，OpenClaw会自动启动MCP服务并配置连接。您可以直接调用以下工具：

- `open_login_page` - 打开登录页并返回二维码
- `monitor_login` - 监控登录状态直到成功
- `publish_draft_from_draftbox` - 发布草稿箱中的文章
- `wait_for_publish_success` - 确认发布成功
- `reset_login_state` - 重置登录状态重新开始

## 技术实现

基于Model Context Protocol (MCP)标准，使用Playwright进行浏览器自动化，支持完整的微信公众号工作流。

## 开发者

- 项目地址: G:\ideaGo\mcpServe
- 版本: 0.1.0