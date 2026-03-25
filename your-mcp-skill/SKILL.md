---
name: "openclaw-wechat-mp"
description: "通过 MCP 控制浏览器完成微信公众号登录与页面流程自动化。Invoke when 需要扫码登录、保存登录态或按步骤点击/等待页面状态。"
version: "0.1.0"
type: "script"  # Changed from "mcp" to "script" to indicate direct script execution
---

# OpenClaw WeChat MP Skill

本技能提供微信公众号自动化功能，包括扫码登录、草稿箱管理和文章发布。

## 安装后配置说明

**重要**: 此技能采用**直接脚本调用模式**，而非标准MCP协议。安装后需要手动运行Python脚本来执行功能。

### 为什么使用直接脚本调用？
- 避免OpenClaw MCP集成层的兼容性问题
- 提供更稳定的执行环境
- 确保所有功能都能正常工作
- 简化调试和故障排除

## 工程结构

```
your-mcp-skill/
├── SKILL.md
├── config/
│   └── default.json
├── mcp-server/
│   ├── pyproject.toml
│   ├── openclaw_wechat_mcp/
│   └── scripts/
│       ├── login_and_wait.py
│       └── publish_end_to_end.py
├── docs/
├── examples/
└── tests/
```

## 安装步骤

### 1. 复制技能目录
将整个 `your-mcp-skill` 目录复制到 `~/.openclaw/extensions/wechat/`

### 2. 安装依赖
```bash
cd ~/.openclaw/extensions/wechat/mcp-server
pip install -r requirements.txt
playwright install chrome
```

### 3. 配置API凭据
编辑 `config/default.json`，填入您的微信公众平台 `appid` 和 `appsecret`：

```json
{
  "wechat_mp": {
    "appid": "your_actual_appid_here",
    "appsecret": "your_actual_appsecret_here"
  }
}
```

## 使用方法（直接脚本调用）

### 登录（单步）
运行登录脚本，会自动打开登录页并监听登录完成：

```bash
cd ~/.openclaw/extensions/wechat/mcp-server
python scripts/login_and_wait.py --timeout_ms 300000 --poll_ms 1000 --headless false --slow_mo_ms 200 --channel chrome
```

### 发布（一键）
运行发布脚本，内部会接口创建草稿→草稿箱发表→自动监听发布成功：

```bash
cd ~/.openclaw/extensions/wechat/mcp-server
python scripts/publish_end_to_end.py \
  --title "您的文章标题" \
  --author "作者名" \
  --content-file "/path/to/article.html" \
  --cover-path "/path/to/cover.jpg" \
  --channel chrome \
  --headless false \
  --slow_mo_ms 200
```

## 脚本参数说明
### 正文图片处理
- 正文中的图片请先下载到本地（绝对路径）。
- 发布过程中会将本地图片上传为素材并返回 URL（在结果的 `structuredContent.cover_url` 字段中提供）。
- 生成 HTML 正文时，将图片以 `<img src="返回的URL">` 的形式插入到内容中；多图请重复“下载→上传→插入”的流程。



### 通用参数
- `--headless false`：打开真实浏览器窗口
- `--slow_mo_ms 200`：放慢点击/跳转，便于观察  
- `--channel chrome`：使用系统Chrome浏览器

### 发布脚本专用参数
- `--title`：中文标题（必填）
- `--author`：作者（可选）
- `--content-file`：HTML内容文件路径（必填）
- `--cover-path`：本地封面图片绝对路径（必填）

## 技术栈

- **运行时**: Python >= 3.11
- **浏览器自动化**: Playwright  
- **执行方式**: 直接Python脚本调用
- **配置管理**: JSON配置文件

## 故障排除

### 常见问题1：脚本找不到模块
**解决方案**：确保在 `mcp-server` 目录下运行脚本，或设置PYTHONPATH

### 常见问题2：缺少API凭据
**解决方案**：在 `config/default.json` 中填入正确的appid和appsecret

### 常见问题3：浏览器驱动问题  
**解决方案**：运行 `playwright install chrome` 确保浏览器驱动已安装

## 示例脚本

### login_and_wait.py
```python
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from openclaw_wechat_mcp.server import login_and_wait
# ... (rest of the script)
```

### publish_end_to_end.py  
```python
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from openclaw_wechat_mcp.server import publish_end_to_end
# ... (rest of the script)
```

## 稳定性提示

- 文本与HTML直接传中文（UTF-8），避免“\\uXXXX”
- `cover_path` 必须是本机存在的图片文件（绝对路径）
- 优先 `channel="chrome"` 或配置 `executable_path` 指向系统Chrome
- `headless=false` 与适当 `slow_mo_ms` 提升稳定性

## 兼容性说明

此技能设计为**独立运行模式**，不依赖OpenClaw的MCP协议层，确保在各种环境下都能稳定工作。
