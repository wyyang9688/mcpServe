---
name: "xhs-mcp-skill"
description: "小红书 MCP 技能：登录、发布图文、回复评论，供 OpenClaw 调用。"
---

# 小红书 MCP 技能

提供最小工具：login_and_wait、publish_image_text、reply_comment。依赖 Chrome 远程调试端口。

## 结构
- xhs-mcp-skill/
  - SKILL.md
  - config/default.json
  - mcp-server/
    - openclaw_xhs_mcp/
      - server.py
    - pyproject.toml
  - scripts/
    - chrome_launcher.py
    - account_manager.py
    - xhs_publish.py

## 最小工具
- login_and_wait：打开登录页并监听登录完成
- publish_image_text：上传图片、填写标题与正文、点击发布
- reply_comment：在指定笔记页回复评论

## 参数
- title、content、images（本地绝对路径数组）
- note_url、text（回复评论）
- headless、account 可选

## 正文图片
- 正文中的 img 标签 src 必须使用本地绝对路径
- 发布时自动上传并替换为 URL（图文模式通过上传区域）

## 依赖与前置
- 安装依赖：requests、websockets（已在 pyproject 声明）
- 本机安装 Google Chrome，并允许远程调试端口 9222
- 首次使用需在非 headless 模式扫码登录

## 工具调用示例
- login_and_wait
  - arguments: { "timeout_ms": 300000, "poll_ms": 1000, "headless": false, "account": "default" }
- publish_image_text
  - arguments: { "title": "测试图文", "content": "正文文本...", "images": ["g:/media/cover.jpg"], "headless": false, "account": "default" }
- reply_comment
  - arguments: { "note_url": "https://www.xiaohongshu.com/explore/NOTE_ID", "text": "这是一条回复", "headless": false, "account": "default" }

## 返回结构
- 统一返回 content（文本型 JSON）、structuredContent（结构化对象）、isError（布尔）
- 登录需要扫码时：structuredContent.requires_user_action=true，user_action="xhs_login"
- 发布成功：structuredContent.ok=true，published=true
- 回复成功：structuredContent.ok=true，replied=true

# 小红书发布流程参考

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

## 写长文模式详细步骤
1-2. 启动 Chrome 和检查登录：同上传图文模式
3. 导航到发布页并点击"写长文"tab：scripts/xhs_publish.py → _click_long_article_tab()
4. 点击"新的创作"：scripts/xhs_publish.py → _click_new_creation()
5. 填写长文标题：scripts/xhs_publish.py → _fill_long_title()
6. 填写长文正文：同上传图文模式
7. 一键排版：scripts/xhs_publish.py → _click_auto_format()
8. 模板选择：scripts/xhs_publish.py → get_template_names() + select_template(name)
9. 下一步并填写发布页描述：scripts/xhs_publish.py → click_next_and_prepare_publish(content)
10. 用户确认并发布

## DOM 选择器参考
注意：前端可能更新，以下选择器基于当前结构，需要时更新 scripts/xhs_publish.py 的 SELECTORS。
- 图片上传：input.upload-input / input[type="file"]
- 标题输入（图文）：input[placeholder*="填写标题"] / input.d-text
- 标题输入（长文）：textarea.d-text[placeholder="输入标题"]
- 正文编辑：div.tiptap.ProseMirror / div.ProseMirror[contenteditable="true"]
- 发布按钮：文本匹配“发布”
- 写长文 tab：文本匹配“写长文”（div.creator-tab）
- 新的创作按钮：文本匹配“新的创作”
- 一键排版按钮：文本匹配“一键排版”
- 模板卡片：.template-card（已选：.template-card.selected）
- 模板名称：.template-card .template-title
- 下一步按钮：文本匹配“下一步”
- 登录检测：URL 包含 login / .user-info, .creator-header

## 错误处理
- Chrome 未启动：端口 9222 无响应 → 运行 chrome_launcher.py 或手动启动
- 找不到 Chrome：非标准安装路径 → 检查安装或在脚本中指定路径
- 未登录：cookie 过期或首次使用 → 在 Chrome 窗口中扫码登录
- 选择器失效：页面更新 → 更新 SELECTORS
- 图片上传失败：路径错误或格式不支持 → 检查文件路径与格式
- 发布按钮找不到：页面未完全加载 → 增加等待或手动点击
