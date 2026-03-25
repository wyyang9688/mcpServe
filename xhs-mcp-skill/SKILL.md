name: "xhs-mcp-skill"
description: "小红书 MCP 技能：登录等待、发布图文、回复评论。基于脚本 xhs_publish.py 与 Chrome DevTools Protocol。"
---

# 小红书 MCP 技能（基于最新脚本）

提供工具：login_and_wait、publish_image_text、reply_comment。所有流程严格调用 scripts/xhs_publish.py 与 scripts/chrome_launcher.py 的现有方法，不虚构接口。依赖 Chrome 远程调试端口。

## 结构
- xhs-mcp-skill/
  - SKILL.md
  - config/default.json
  - mcp-server/
    - openclaw_xhs_mcp/
      - server.py（导出 FastMCP，方法调用脚本步骤）
      - __main__.py（python -m openclaw_xhs_mcp 入口）
      - index.py（mcp.run()）
    - pyproject.toml
  - scripts/
    - chrome_launcher.py
    - account_manager.py
    - xhs_publish.py

## 工具
- login_and_wait：打开登录页并轮询登录完成（connect → open_login_page → check_login）
- publish_image_text：上传本地图片、填写标题与正文并点击发布（navigate → click tab → upload → fill title → fill content → click publish）
- publish_long_article：长文模式发布（navigate → click long tab → new creation → fill long title → fill content → auto format → select template（可选） → next step → click publish）
- reply_comment：在指定笔记页回复评论（navigate → fill comment → click submit）

## 参数
- 通用：headless（bool，可选）、account（string，可选）
- publish_image_text：title（string）、content（string），images（string[]，本地绝对路径）
- publish_long_article：title（string）、content（string）、template_name（string，可选）
- reply_comment：note_url（string）、text（string）

## 正文与图片
- content 作为纯文本处理：按换行拆分为段落写入编辑器（TipTap/ProseMirror），不解析其中的 HTML img 标签
- 图片通过 images 参数上传：必须使用本地绝对路径，脚本用 DOM.setFileInputFiles 完成上传
- 同时支持“上传图文”与“写长文”模式；写长文可选模板名，不提供正文中 img 标签解析

## 依赖与前置
- 安装依赖：requests、websockets（已在 pyproject 声明）
- 本机安装 Google Chrome，并允许远程调试端口 9222
- 首次使用需在非 headless 模式扫码登录
- 多账号与持久化：由 chrome_launcher 管理独立 profile 目录，account 可选切换

## 工具调用示例
- login_and_wait
  - arguments: { "timeout_ms": 300000, "poll_ms": 1000, "headless": false, "account": "default" }
- publish_image_text
  - arguments: { "title": "测试图文", "content": "正文文本...", "images": ["g:/media/1.jpg","g:/media/2.jpg"], "headless": false, "account": "default" }
- reply_comment
  - arguments: { "note_url": "https://www.xiaohongshu.com/explore/NOTE_ID", "text": "这是一条回复", "headless": false, "account": "default" }

## 返回结构
- 统一返回 content（文本型 JSON）、structuredContent（结构化对象）、isError（布尔）
- 登录需要扫码时：structuredContent.requires_user_action=true，user_action="xhs_login"
- 发布成功：structuredContent.ok=true，published=true
- 回复成功：structuredContent.ok=true，replied=true

## 启动方式
- Inspector：在仓库根目录运行 npm run inspector:xhs
- 直接运行：cd xhs-mcp-skill/mcp-server 后执行 python -m openclaw_xhs_mcp

# 发布流程参考（与脚本一致）

本文档描述通过 CDP（Chrome DevTools Protocol）自动发布内容到小红书创作者中心的完整流程。

## 前置条件

1. Chrome 浏览器已安装（Google Chrome）
2. Python 依赖已安装：websockets、requests
3. 首次登录已完成（cookie 持久化在专用 profile 中）

## 流程概览

上传图文模式:
生成文案 → 用户确认 → 启动 Chrome → 检查登录 → 导航发布页 → 上传图片 → 填写标题 → 填写正文 → 用户确认发布

写长文模式:
生成文案 → 用户确认 → 启动 Chrome → 检查登录 → 导航发布页 → 点击"写长文"tab → 点击"新的创作" → 填写标题 → 填写正文 → 一键排版 → 用户选择模板 → 下一步 → 填写发布页正文描述 → 用户确认发布

## 详细步骤

### 1. 启动 / 连接 Chrome
脚本: scripts/chrome_launcher.py
- 检测 127.0.0.1:9222 端口是否已有 Chrome
- 若无，启动 Chrome 并附带参数：
  - --remote-debugging-port=9222
  - --user-data-dir=%LOCALAPPDATA%/Google/Chrome/XiaohongshuProfile
  - --no-first-run
  - --no-default-browser-check
  - --headless=new（在无头模式下）
- 等待端口就绪（最多 15 秒）
用户数据目录说明：使用独立的 XiaohongshuProfile 目录，与用户日常浏览器 profile 完全隔离。
无头模式说明：登录或切换账号会自动切换到有窗口模式。

### 2. 检查登录状态
脚本: scripts/xhs_publish.py → check_login()
- 导航 https://creator.xiaohongshu.com
- 检查当前 URL 是否包含 login（被重定向）
- 若未登录，提示在 Chrome 窗口中扫码登录

### 3. 导航到发布页
- 目标 URL: https://creator.xiaohongshu.com/publish/publish
- 等待页面完全加载

### 4. 上传图片
脚本: scripts/xhs_publish.py → _upload_images()
- 通过 CDP DOM.querySelector 定位 input[type="file"]
- 使用 DOM.setFileInputFiles 设置文件路径
- 等待图片上传和处理完成

### 5. 填写标题
脚本: scripts/xhs_publish.py → _fill_title()
- 定位标题输入框
- 设置 value 并触发 input/change

### 6. 填写正文
脚本: scripts/xhs_publish.py → _fill_content()
- 定位 contenteditable 编辑区域（TipTap/ProseMirror）
- 正文按段落拆分为 <p> 并写入 innerHTML，段落之间插入 <p><br></p>
- 触发 input

### 7. 用户确认并发布
- 脚本填写完成后提示用户在浏览器中检查预览
- 用户确认后点击发布按钮（或脚本点击）

> 注：写长文模式相关方法存在于脚本中，但当前 MCP 工具未暴露该模式；如需启用，请在 server.py 增加对应方法并更新插件工具列表。

## DOM 选择器参考
注意：前端可能更新，以下选择器基于当前结构，需要时更新 scripts/xhs_publish.py 的 SELECTORS。
- 图片上传：input.upload-input / input[type="file"]
- 标题输入（图文）：input[placeholder*="填写标题"] / input.d-text
- 正文编辑：div.tiptap.ProseMirror / div.ProseMirror[contenteditable="true"]
- 发布按钮：文本匹配“发布”
- 登录检测：URL 包含 login / .user-info, .creator-header

## 错误处理
- Chrome 未启动：端口 9222 无响应 → 运行 chrome_launcher.py 或手动启动
- 找不到 Chrome：非标准安装路径 → 检查安装或在脚本中指定路径
- 未登录：cookie 过期或首次使用 → 在 Chrome 窗口中扫码登录
- 选择器失效：页面更新 → 更新 SELECTORS
- 图片上传失败：路径错误或格式不支持 → 检查文件路径与格式
- 发布按钮找不到：页面未完全加载 → 增加等待或手动点击
