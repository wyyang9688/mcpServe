---
name: "openclaw-wechat-publish"
description: "通过 MCP 完成公众号接口建草稿与浏览器发表。Invoke 当需要：生成标题/HTML正文/作者、保存封面并一键发布到公众号。"
---

# OpenClaw 公众号发布技能

该技能通过 MCP 工具完成整条发布链路：生成标题 → 生成排版 HTML 正文 → 设置作者 → 保存本地封面 → 接口创建草稿 → 草稿箱定位并浏览器发表 → 轮询验证成功（支持扫码验证）。

**何时调用**
- 已生成文章三要素（标题/作者/HTML正文），并在本机有封面图片。
- 需要一键完成“接口创建草稿 → 浏览器发表 → 成功确认”的自动化流程。
- 或仅需接口侧创建草稿用于后续人工操作。

## 前置条件
- MCP Server 已运行并具备浏览器自动化与接口权限。
- 具备公众号接口凭据 appid、appsecret（建议运行时传参，不写入仓库）。
- 封面图片已保存到本机，可读的绝对路径（建议使用正斜杠路径或 JSON 中双反斜杠）。

## 工具列表
- create_draft_then_publish：接口创建草稿后，在草稿箱定位并“发表”，最后轮询验证成功。
- publish_draft_api：仅通过接口创建草稿（返回 media_id），不进行浏览器发表。
- publish_article：浏览器内“写新文章”并发表（不走接口）。

## 参数说明
- title: 文章标题（字符串，中文直接传入，避免“\\uXXXX”）
- author: 作者名（字符串）
- content: 正文内容（字符串，支持 HTML 排版）
- cover_path: 本地封面图片绝对路径（必填，联动/接口草稿工具）
- 选填浏览器参数：headless（布尔）、slow_mo_ms（毫秒）、channel（如 "chrome"）、executable_path（浏览器可执行路径）
- 选填凭据：appid、appsecret（不传则从配置读取）

## 快速流程（推荐联动）
1. OpenClaw 生成中文标题 → 作为 title 传入
2. OpenClaw 生成排版后的 HTML 正文（UTF-8）→ 作为 content 传入
3. OpenClaw 生成作者名 → 作为 author 传入
4. 将封面图片保存到本机（绝对路径）→ 作为 cover_path 传入
5. 调用 create_draft_then_publish 完成接口建草稿与浏览器发表

## 调用示例

### 联动：接口草稿 → 草稿箱发表 → 成功确认
```json
{
  "name": "create_draft_then_publish",
  "arguments": {
    "title": "示例标题：浅色流光专题",
    "author": "浅色流光",
    "content": "<h1>示例标题</h1><p>这是由 OpenClaw 生成的排版HTML。</p>",
    "cover_path": "g:/xwechat_files/wyyang9688_f676/business/favorite/temp/1.jpg",
    "channel": "chrome",
    "headless": false,
    "slow_mo_ms": 200
  }
}
```

### 仅接口创建草稿
```json
{
  "name": "publish_draft_api",
  "arguments": {
    "title": "示例标题：接口草稿",
    "author": "浅色流光",
    "content": "<p>接口创建草稿正文HTML</p>",
    "cover_path": "g:/xwechat_files/wyyang9688_f676/business/favorite/temp/1.jpg"
  }
}
```

### 浏览器直发新文章（不走接口）
```json
{
  "name": "publish_article",
  "arguments": {
    "title": "浏览器直发标题",
    "author": "浅色流光",
    "content": "<p>这里是正文HTML</p>",
    "channel": "chrome",
    "headless": false,
    "slow_mo_ms": 200
  }
}
```

## 返回结果
- 成功联动：
  - ok: true
  - published: true
  - url: 重定向到公众号首页（以 https://mp.weixin.qq.com/cgi-bin/home 开头）
  - matched_title: 首页“近期发表”是否匹配标题
  - media_id: 接口创建的草稿 media_id
  - results: 步骤记录（token/上传封面/创建草稿/草稿箱发表/成功轮询）
- 需要扫码：
  - ok: false
  - requires_user_action: true
  - user_action: "wechat_verify"
  - qr: {data_url, base64, sha256…}（OpenClaw 应推送到模型或前端以完成扫码）
- 失败：
  - ok: false
  - error: 错误详情
  - results: 步骤记录

## 编码与稳定性提示
- 内容编码：请直接用中文与 HTML，避免手写“\\uXXXX”。工具已做转义检测与自动解码；但推荐上游生成真实 UTF-8 字符串。
- 路径格式：使用绝对路径；推荐 g:/.../1.jpg 或 g:\\\\...\\\\1.jpg。
- 浏览器参数：优先使用 channel="chrome" 或配置 executable_path 指向系统 Chrome；headless=false 与适当 slow_mo_ms 提升稳定性。
- 接口 token：若稳定版 token 因 IP 白名单报 40164，会自动回退到老接口获取 token。
