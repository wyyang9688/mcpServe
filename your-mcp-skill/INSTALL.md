# OpenClaw WeChat MP Skill - 安装指南

## 安装步骤

### 1. 复制技能目录
将整个 `your-mcp-skill` 目录复制到 OpenClaw 的 extensions 目录：
```
~/.openclaw/extensions/wechat/
```

### 2. 安装Python依赖
```bash
cd ~/.openclaw/extensions/wechat/mcp-server
pip install -r requirements.txt
playwright install chrome
```

### 3. 配置微信公众平台API
编辑 `config/default.json` 文件，替换以下字段：
- `wechat_mp.appid`: 您的微信公众平台AppID
- `wechat_mp.appsecret`: 您的微信公众平台AppSecret

### 4. 验证安装
运行登录脚本测试安装是否成功：
```bash
cd ~/.openclaw/extensions/wechat/mcp-server
python scripts/login_and_wait.py --timeout_ms 30000 --headless false
```

## 使用方法

### 登录微信公众号
```bash
python scripts/login_and_wait.py \
  --timeout_ms 300000 \
  --poll_ms 1000 \
  --headless false \
  --slow_mo_ms 200 \
  --channel chrome
```

### 发布文章
```bash
python scripts/publish_end_to_end.py \
  --title "文章标题" \
  --author "作者名" \
  --content-file "/path/to/article.html" \
  --cover-path "/path/to/cover.jpg" \
  --channel chrome \
  --headless false \
  --slow_mo_ms 200
```

## 故障排除

### 常见问题
1. **ModuleNotFoundError**: 确保在 `mcp-server` 目录下运行脚本
2. **缺少API凭据**: 检查 `config/default.json` 中的 appid 和 appsecret
3. **浏览器驱动问题**: 运行 `playwright install chrome`

### 调试模式
添加 `--headless false --slow_mo_ms 500` 参数来观察浏览器操作过程。

## 注意事项

- 此技能使用**直接脚本调用模式**，不依赖OpenClaw的MCP协议层
- 确保您的系统已安装Python 3.11+
- 封面图片必须是有效的JPG/PNG文件
- 文章内容必须是有效的HTML格式