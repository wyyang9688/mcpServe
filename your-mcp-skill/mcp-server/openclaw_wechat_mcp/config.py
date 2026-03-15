import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class BrowserViewport(BaseModel):
    width: int = 1280
    height: int = 720


class BrowserConfig(BaseModel):
    type: str = "chromium"
    headless: bool = True
    channel: str | None = None
    executable_path: str | None = None
    use_system_fallback: bool = True
    slow_mo_ms: int = 0
    viewport: BrowserViewport = BrowserViewport()
    locale: str | None = "zh-CN"
    timezone_id: str | None = "Asia/Shanghai"
    user_agent: str | None = None


class SessionConfig(BaseModel):
    profile_dir: str = "data/playwright-profile"


class WechatMPConfig(BaseModel):
    login_url: str = "https://mp.weixin.qq.com/"
    qr_selectors: list[str] = [
        "img.qrcode",
        "img.qr_img",
        "img[src*=\"qrcode\"]",
        "#qrCode img",
        "canvas",
    ]
    logged_in_indicators: list[str] = ["text=公众号平台"]


class AppConfig(BaseModel):
    browser: BrowserConfig = BrowserConfig()
    session: SessionConfig = SessionConfig()
    wechat_mp: WechatMPConfig = WechatMPConfig()


def _find_default_config_path() -> Path:
    for base in [Path.cwd(), Path(__file__).resolve()]:
        for parent in [base, *base.parents]:
            candidate = parent / "config" / "default.json"
            if candidate.exists():
                return candidate
    raise FileNotFoundError("config/default.json not found")


def load_config(config_path: str | None = None) -> AppConfig:
    path = (
        Path(config_path)
        if config_path
        else Path(os.environ.get("OPENCLAW_MCP_CONFIG", "")).expanduser()
        if os.environ.get("OPENCLAW_MCP_CONFIG")
        else _find_default_config_path()
    )
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)


def resolve_data_path(path_like: str) -> Path:
    p = Path(path_like)
    if p.is_absolute():
        return p
    return Path.cwd() / p

