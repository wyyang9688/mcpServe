# OpenClaw WeChat MP MCP

## 配置

默认配置在 `config/default.json`。

常用项：

- `wechat_mp.login_url`: 登录入口 URL
- `wechat_mp.qr_selectors`: 二维码元素的候选选择器列表（按顺序尝试）
- `session.profile_dir`: Playwright 持久化 profile 目录（用于保存登录态）
- `browser.headless`: 是否无头模式
- `browser.channel`: 使用系统浏览器通道（例如 `msedge` / `chrome`），可避免下载 Playwright 浏览器

## 启动

在 `mcp-server/` 下：

1. 安装依赖
2. 安装浏览器：`playwright install chromium`
3. 启动：`python -m openclaw_wechat_mcp`

## 工具调用（示例）

参考 [basic-usage.json](../examples/basic-usage.json)。

## 测试

参考 [TESTING.md](./TESTING.md)。

## 工具列表

- `open_login_page(url?, return_qr?, headless?, slow_mo_ms?, channel?, executable_path?)`: 打开登录页；未登录时返回二维码（含 base64/data_url/选择器/图片源地址等）
- `wait_for_login(timeout_ms?, poll_ms?)`: 等待扫码登录成功（轮询检测）
- `monitor_login(timeout_ms?, poll_ms?, url?, headless?, slow_mo_ms?, channel?, executable_path?, push_qr_on_change?)`: 监控扫码/过期/登录阶段，并推送阶段消息
- `get_login_status()`: 获取当前登录状态
- `reset_login_state()`: 清理持久化 profile，用于重新登录
- `run_web_steps(steps, url?)`: 按步骤执行点击/等待/脚本并返回执行结果
