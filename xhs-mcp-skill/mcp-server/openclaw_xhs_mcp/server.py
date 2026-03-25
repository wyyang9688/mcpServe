import sys
import os
import json
import time
from typing import Any

try:
    from mcp import tool as mcp_tool
except Exception:
    def mcp_tool():
        def deco(fn):
            return fn
        return deco

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scripts_dir = os.path.join(base_dir, "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from chrome_launcher import ensure_chrome, restart_chrome
from xhs_publish import XiaohongshuPublisher

def _resp(sc: dict) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
        "structuredContent": sc,
        "isError": False,
    }

@mcp_tool()
async def login_and_wait(timeout_ms: int = 300000, poll_ms: int = 1000, headless: bool = False, account: str | None = None) -> dict[str, Any]:
    ok = ensure_chrome(headless=headless, account=account)
    if not ok:
        return _resp({"ok": False, "error": "chrome_not_available"})
    pub = XiaohongshuPublisher()
    pub.connect()
    pub.open_login_page()
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        if pub.check_login():
            return _resp({"ok": True, "logged_in": True})
        time.sleep(max(0.2, poll_ms / 1000.0))
    return _resp({"ok": False, "logged_in": False, "requires_user_action": True, "user_action": "xhs_login"})

@mcp_tool()
async def check_login(headless: bool = False, account: str | None = None) -> dict[str, Any]:
    ok = ensure_chrome(headless=headless, account=account)
    if not ok:
        return _resp({"ok": False, "error": "chrome_not_available"})
    pub = XiaohongshuPublisher()
    pub.connect()
    logged = pub.check_login()
    return _resp({"ok": True, "logged_in": bool(logged)})

@mcp_tool()
async def login(headless: bool = False, account: str | None = None) -> dict[str, Any]:
    restart_chrome(headless=False, account=account)
    pub = XiaohongshuPublisher()
    pub.connect()
    pub.open_login_page()
    return _resp({"ok": False, "requires_user_action": True, "user_action": "xhs_login"})

@mcp_tool()
async def publish_image_text(title: str, content: str, images: list[str], headless: bool = False, account: str | None = None) -> dict[str, Any]:
    ok = ensure_chrome(headless=headless, account=account)
    if not ok:
        return _resp({"ok": False, "error": "chrome_not_available"})
    pub = XiaohongshuPublisher()
    pub.connect()
    if not pub.check_login():
        return _resp({"ok": False, "requires_user_action": True, "user_action": "xhs_login"})
    pub.publish(title=title, content=content, image_paths=images)
    pub._click_publish()
    return _resp({"ok": True, "published": True, "title": title})

@mcp_tool()
async def publish(title: str, content: str, images: list[str], headless: bool = False, account: str | None = None) -> dict[str, Any]:
    ok = ensure_chrome(headless=headless, account=account)
    if not ok:
        return _resp({"ok": False, "error": "chrome_not_available"})
    pub = XiaohongshuPublisher()
    pub.connect()
    if not pub.check_login():
        return _resp({"ok": False, "requires_user_action": True, "user_action": "xhs_login"})
    pub.publish(title=title, content=content, image_paths=images)
    pub._click_publish()
    return _resp({"ok": True, "published": True, "title": title})

@mcp_tool()
async def reply_comment(note_url: str, text: str, headless: bool = False, account: str | None = None) -> dict[str, Any]:
    ok = ensure_chrome(headless=headless, account=account)
    if not ok:
        return _resp({"ok": False, "error": "chrome_not_available"})
    pub = XiaohongshuPublisher()
    pub.connect()
    if not pub.check_login():
        return _resp({"ok": False, "requires_user_action": True, "user_action": "xhs_login"})
    pub.reply_comment(note_url, text)
    return _resp({"ok": True, "replied": True, "note_url": note_url})
