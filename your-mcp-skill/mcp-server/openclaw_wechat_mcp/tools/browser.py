from __future__ import annotations

import asyncio
import base64
import hashlib
import time
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import Page, async_playwright

from ..config import AppConfig, load_config, resolve_data_path


@dataclass
class QrImage:
    mime: str
    base64_data: str
    data_url: str
    selector: str
    source_url: str | None
    file_path: str | None
    sha256: str
    bytes_len: int
    base64_len: int


@dataclass(frozen=True)
class LoginStage:
    stage: str
    detail: str | None = None


class BrowserManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._cfg: AppConfig | None = None
        self._pw: Any | None = None
        self._context: Any | None = None
        self._page: Page | None = None
        self._launch_overrides: dict[str, Any] = {}

    async def _ensure_started(self) -> None:
        if self._page is not None:
            return
        self._cfg = load_config()
        profile_dir = resolve_data_path(self._cfg.session.profile_dir)
        profile_dir.mkdir(parents=True, exist_ok=True)

        self._pw = await async_playwright().start()
        type_name = (self._cfg.browser.type or "chromium").lower()
        if type_name in ["chromium", "chrome", "msedge", "edge"]:
            browser_type = self._pw.chromium
        else:
            browser_type = getattr(self._pw, type_name)
        headless = self._launch_overrides.get("headless", self._cfg.browser.headless)
        slow_mo_ms = self._launch_overrides.get("slow_mo_ms", self._cfg.browser.slow_mo_ms)
        launch_kwargs: dict[str, Any] = {
            "user_data_dir": str(profile_dir),
            "headless": headless,
            "slow_mo": slow_mo_ms,
            "viewport": {
                "width": self._cfg.browser.viewport.width,
                "height": self._cfg.browser.viewport.height,
            },
            "locale": self._cfg.browser.locale,
            "timezone_id": self._cfg.browser.timezone_id,
            "user_agent": self._cfg.browser.user_agent,
        }
        if self._launch_overrides.get("channel"):
            launch_kwargs["channel"] = self._launch_overrides["channel"]
        if self._launch_overrides.get("executable_path"):
            launch_kwargs["executable_path"] = self._launch_overrides["executable_path"]
        if "channel" not in launch_kwargs:
            if type_name in ["chrome", "msedge", "edge"] and not self._cfg.browser.channel:
                launch_kwargs["channel"] = "msedge" if type_name in ["msedge", "edge"] else "chrome"
        if self._cfg.browser.channel:
            launch_kwargs["channel"] = self._cfg.browser.channel
        if self._cfg.browser.executable_path:
            launch_kwargs["executable_path"] = self._cfg.browser.executable_path

        try:
            self._context = await browser_type.launch_persistent_context(**launch_kwargs)
        except Exception as e:
            msg = str(e)
            if (
                self._cfg.browser.use_system_fallback
                and "Executable doesn't exist" in msg
                and "channel" not in launch_kwargs
                and "executable_path" not in launch_kwargs
            ):
                launch_kwargs["channel"] = "msedge"
                self._context = await browser_type.launch_persistent_context(**launch_kwargs)
            else:
                raise
        pages = list(self._context.pages)
        self._page = pages[0] if pages else await self._context.new_page()

    async def get_page(self, launch_overrides: dict[str, Any] | None = None) -> Page:
        async with self._lock:
            if launch_overrides is not None and launch_overrides != self._launch_overrides:
                self._launch_overrides = dict(launch_overrides)
                if self._page is not None:
                    await self.close()
            await self._ensure_started()
            assert self._page is not None
            return self._page

    async def close(self) -> None:
        async with self._lock:
            if self._context is not None:
                await self._context.close()
            self._context = None
            self._page = None
            if self._pw is not None:
                await self._pw.stop()
            self._pw = None


_browser = BrowserManager()


async def open_url(
    url: str,
    wait_until: str = "domcontentloaded",
    *,
    headless: bool | None = None,
    slow_mo_ms: int | None = None,
    channel: str | None = None,
    executable_path: str | None = None,
) -> Page:
    overrides: dict[str, Any] = {}
    if headless is not None:
        overrides["headless"] = headless
    if slow_mo_ms is not None:
        overrides["slow_mo_ms"] = slow_mo_ms
    if channel is not None:
        overrides["channel"] = channel
    if executable_path is not None:
        overrides["executable_path"] = executable_path
    page = await _browser.get_page(overrides if overrides else None)
    await page.goto(url, wait_until=wait_until)
    return page


async def _try_get_qr_from_selector(page: Page, selector: str) -> QrImage | None:
    locator = page.locator(selector).first
    try:
        await locator.wait_for(state="visible", timeout=15000)
        source_url: str | None = None
        try:
            tag = await locator.evaluate("el => (el && el.tagName ? el.tagName.toLowerCase() : '')")
            if tag == "img":
                source_url = await locator.get_attribute("src")
        except Exception:
            source_url = None

        png_bytes = await locator.screenshot(type="png")
        b64 = base64.b64encode(png_bytes).decode("ascii")
        sha256 = hashlib.sha256(png_bytes).hexdigest()
        data_url = f"data:image/png;base64,{b64}"

        file_path: str | None = None
        try:
            out_dir = resolve_data_path("data/qr")
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / f"qr-{int(time.time() * 1000)}.png"
            out.write_bytes(png_bytes)
            file_path = str(out)
        except Exception:
            file_path = None

        return QrImage(
            mime="image/png",
            base64_data=b64,
            data_url=data_url,
            selector=selector,
            source_url=source_url,
            file_path=file_path,
            sha256=sha256,
            bytes_len=len(png_bytes),
            base64_len=len(b64),
        )
    except Exception:
        return None


async def extract_qr_base64(page: Page, selectors: list[str]) -> QrImage:
    last_error: str | None = None
    for selector in selectors:
        qr = await _try_get_qr_from_selector(page, selector)
        if qr:
            return qr
        last_error = f"二维码元素未找到或不可见: {selector}"
    raise RuntimeError(last_error or "二维码提取失败")


async def is_logged_in(page: Page, indicators: list[str]) -> bool:
    for indicator in indicators:
        try:
            locator = page.locator(indicator).first
            if await locator.is_visible(timeout=1000):
                return True
        except Exception:
            continue
    return False


async def detect_login_stage(page: Page, logged_in_indicators: list[str]) -> LoginStage:
    if await is_logged_in(page, logged_in_indicators):
        return LoginStage(stage="logged_in")
    body = (await page.locator("body").inner_text(timeout=3000)) or ""
    if any(s in body for s in ["二维码已失效", "二维码失效", "已过期", "点击刷新", "刷新二维码"]):
        return LoginStage(stage="qr_expired")
    if any(s in body for s in ["扫码成功", "请在手机上确认", "在手机上确认", "已扫描"]):
        return LoginStage(stage="scanned_pending_confirm")
    return LoginStage(stage="await_scan")


def get_profile_dir() -> Path:
    cfg = load_config()
    return resolve_data_path(cfg.session.profile_dir)


async def reset_session() -> Path:
    profile_dir = get_profile_dir()
    await _browser.close()
    if profile_dir.exists():
        shutil.rmtree(profile_dir, ignore_errors=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir

