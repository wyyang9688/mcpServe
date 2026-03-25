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
  - `login_and_wait`: 打开登录页并自动监听登录完成
  - `publish_end_to_end`: 接口建草稿 + 草稿箱发表 + 自动监听发布成功

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

### 登录（单步）

仅调用 `login_and_wait`，会自动打开登录页并监听登录完成（默认超时 300000ms，间隔 1000ms）。示例：

```json
{ "name": "login_and_wait", "arguments": { "timeout_ms": 300000, "poll_ms": 1000, "headless": false, "slow_mo_ms": 200, "channel": "chrome" } }
```

### 发布（一键）

仅调用 `publish_end_to_end`，内部会接口创建草稿→草稿箱发表→自动监听发布成功（默认超时 180000ms，间隔 1000ms）。如出现“微信验证”，返回 `requires_user_action=true` 与 `qr` 用于扫码，扫码后再次调用继续。示例：

```json
{
  "name": "publish_end_to_end",
  "arguments": {
    "title": "示例标题",
    "author": "浅色流光",
    "content": "<p>OpenClaw 生成的排版HTML</p>",
    "cover_path": "g:/path/to/cover.jpg",
    "channel": "chrome",
    "headless": false,
    "slow_mo_ms": 200
  }
}
```

### 正文图片处理
- 正文中的图片请先下载到本地（绝对路径）。
- 发布过程中会将本地图片上传为素材并返回 URL（在结果的 `structuredContent.cover_url` 字段中提供）。
- 生成 HTML 正文时，将图片以 `<img src="返回的URL">` 的形式插入到内容中；多图请重复“下载→上传→插入”的流程。

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

## 发布工具（OpenClaw WeChat Publish）

该模块提供从生成内容到发布的整链路能力：生成标题 → 生成排版 HTML 正文 → 设置作者 → 保存封面 → 接口创建草稿 → 草稿箱发表 → 发布成功确认（含扫码）。

**何时调用**
- 已生成标题/作者/HTML 正文，并已将封面图片保存到本机。
- 需要一键完成接口建草稿与浏览器发表。

**工具入口（仅暴露两项）**
- `login_and_wait`：打开登录页并自动监听登录完成（返回二维码与状态）
- `publish_end_to_end`：接口创建草稿 + 草稿箱发表 + 自动监听发布成功（最小一键发布）

**参数**
- `title`：中文标题（避免传“\\uXXXX”）
- `author`：作者
- `content`：正文（支持 HTML）
- `cover_path`：本地封面图片绝对路径（必填，接口/联动工具）
- 选填：`headless`、`slow_mo_ms`、`channel`、`executable_path`、`appid`、`appsecret`

**联动示例（一键发布）**
```json
{
  "name": "publish_end_to_end",
  "arguments": {
    "title": "示例标题：浅色流光专题",
    "author": "浅色流光",
    "content": "<h1>示例标题</h1><p>由 OpenClaw 生成的排版HTML。</p>",
    "cover_path": "g:/xwechat_files/wyyang9688_f676/business/favorite/temp/1.jpg",
    "channel": "chrome",
    "headless": false,
    "slow_mo_ms": 200
  }
}
```

（如需仅接口创建草稿或浏览器直发，请使用内部方法，但默认不对外暴露）

**返回与扫码**
- 成功：`ok=true`、`published=true`、`url` 指向首页、`matched_title` 表示近期发表匹配。
- 需要扫码：返回 `requires_user_action=true` 与 `qr`（data_url/base64/sha256）；扫码后继续。
- 失败：`ok=false`，附带 `error` 与步骤 `results`。

**稳定性提示**
- 文本与 HTML 直接传中文（UTF-8），避免“\\uXXXX”；模块内部已做自动解码。
- `cover_path` 必须是本机存在的图片文件（绝对路径）。
- 优先 `channel="chrome"` 或配置 `executable_path` 指向系统 Chrome；`headless=false` 与适当 `slow_mo_ms` 提升稳定性。
- 稳定版 token 若因 IP 白名单报 `40164`，模块会自动回退到老接口获取 token。

## 最小接口（推荐给 OpenClaw）

- 登录（单步）：
-  调用 `login_and_wait`：会打开登录页、返回二维码，并自动监听登录完成（默认超时 300000ms，间隔 1000ms）
  示例：
  ```json
  { "name": "login_and_wait", "arguments": { "timeout_ms": 300000, "poll_ms": 1000, "headless": false, "slow_mo_ms": 200, "channel": "chrome" } }
  ```
- 发布（联动一键）：
  - 仅调用 `publish_end_to_end`，内部会：
    - 接口创建草稿（需 `cover_path` 必填、`title/author/content`）
    - 草稿箱定位并点击“发表”
    - 自动调用 `wait_for_publish_success` 监听发布成功（默认超时 180000ms，间隔 1000ms）
  - 遇到“微信验证”会返回 `requires_user_action=true` 与 `qr` 用于扫码，扫码后流程继续
  示例：
  ```json
  {
    "name": "publish_end_to_end",
    "arguments": {
      "title": "示例标题",
      "author": "浅色流光",
      "content": "<p>OpenClaw 生成的排版HTML</p>",
      "cover_path": "g:/path/to/cover.jpg",
      "channel": "chrome",
      "headless": false,
      "slow_mo_ms": 200
    }
  }
  ```
