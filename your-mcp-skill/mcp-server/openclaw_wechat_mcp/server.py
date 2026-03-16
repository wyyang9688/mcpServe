from __future__ import annotations

import asyncio
from typing import Any
from datetime import datetime
import builtins

from mcp.server.fastmcp import Context, FastMCP

from .config import load_config, resolve_data_path
from .tools.browser import (
    detect_login_stage,
    extract_qr_base64,
    get_profile_dir,
    is_logged_in,
    open_url,
    reset_session,
 )


mcp = FastMCP("openclaw-wechat-mp-mcp")

_builtin_print = builtins.print

def _log_to_file(message: str) -> None:
    try:
        log_path = resolve_data_path("data/mcp.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{ts} {message}\n")
    except Exception:
        pass

def print(*args, **kwargs):  # module-local print wrapper: write to file and stdout
    try:
        msg = " ".join(str(a) for a in args)
        _log_to_file(msg)
    except Exception:
        pass
    return _builtin_print(*args, **kwargs)

async def _poll_login_and_notify(page: Any, poll_ms: int, login_timeout_ms: int, ctx: Context | None) -> None:
    try:
        cfg = load_config()
        indicators = cfg.wechat_mp.logged_in_indicators
        home_prefixes = cfg.wechat_mp.home_url_prefixes
        loop = asyncio.get_running_loop()
        deadline = loop.time() + (login_timeout_ms / 1000)
        while loop.time() < deadline:
            if await is_logged_in(page, indicators, home_prefixes):
                try:
                    print(f"[open_login_page/poller] login detected url={page.url}")
                except Exception:
                    print("[open_login_page/poller] login detected")
                if ctx is not None:
                    try:
                        await ctx.info(f"login_success url={getattr(page, 'url', None)} profile_dir={str(get_profile_dir())}")
                    except Exception:
                        pass
                return
            try:
                print(f"[open_login_page/poller] waiting login url={page.url}")
            except Exception:
                print("[open_login_page/poller] waiting login")
            if ctx is not None:
                try:
                    await ctx.info(f"login_poll_wait url={getattr(page, 'url', None)}")
                except Exception:
                    pass
            await asyncio.sleep(poll_ms / 1000)
        print("[open_login_page/poller] login wait timed out")
        if ctx is not None:
            try:
                await ctx.info(f"login_timeout profile_dir={str(get_profile_dir())}")
            except Exception:
                pass
    except Exception as e:
        print(f"[open_login_page/poller] error: {e}")
        if ctx is not None:
            try:
                await ctx.error(f"login_poll_error {str(e)}")
            except Exception:
                pass


@mcp.tool()
async def open_login_page(
    ctx: Context,
    url: str | None = None,
    return_qr: bool = True,
    headless: bool | None = None,
    slow_mo_ms: int | None = None,
    channel: str | None = None,
    executable_path: str | None = None,
    poll_login: bool = True,
    poll_ms: int = 3000,
    login_timeout_ms: int = 120000,
) -> dict[str, Any]:
    cfg = load_config()
    target_url = url or cfg.wechat_mp.login_url
    print(f"[open_login_page] navigate url={target_url}")
    try:
        await ctx.info(f"navigate url={target_url}")
    except Exception:
        pass
    page = await open_url(
        target_url,
        headless=headless,
        slow_mo_ms=slow_mo_ms,
        channel=channel,
        executable_path=executable_path,
    )
    try:
        print(f"[open_login_page] page url={page.url}")
    except Exception:
        print("[open_login_page] page url unavailable")
    logged_in = await is_logged_in(page, cfg.wechat_mp.logged_in_indicators, cfg.wechat_mp.home_url_prefixes)
    print(f"[open_login_page] logged_in={logged_in}")
    qr_payload: dict[str, Any] | None = None
    if return_qr and not logged_in:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 45
        while loop.time() < deadline and qr_payload is None:
            print("[open_login_page] trying to detect login stage and capture qr")
            stage = await detect_login_stage(page, cfg.wechat_mp.logged_in_indicators, cfg.wechat_mp.home_url_prefixes)
            print(f"[open_login_page] stage={stage.stage}")
            if stage.stage in ["await_scan", "qr_expired"]:
                try:
                    qr = await extract_qr_base64(page, cfg.wechat_mp.qr_selectors)
                    qr_payload = {
                        "mime": qr.mime,
                        "base64": qr.base64_data,
                        "data_url": qr.data_url,
                        "selector": qr.selector,
                        "source_url": qr.source_url,
                        "file_path": qr.file_path,
                        "sha256": qr.sha256,
                        "bytes_len": qr.bytes_len,
                        "base64_len": qr.base64_len,
                    }
                    print("[open_login_page] qr captured")
                    try:
                        await ctx.info(f"qr_captured selector={qr.selector} sha256={qr.sha256}")
                    except Exception:
                        pass
                    break
                except Exception:
                    print("[open_login_page] qr capture failed, will retry")
                    qr_payload = None
            await asyncio.sleep(1)
    if poll_login:
        try:
            await ctx.info(f"login_poll_started interval_ms={poll_ms} timeout_ms={login_timeout_ms}")
        except Exception:
            pass
        asyncio.create_task(_poll_login_and_notify(page, poll_ms, login_timeout_ms, ctx))
    return {
        "url": target_url,
        "logged_in": logged_in,
        "qr": qr_payload,
        "profile_dir": str(get_profile_dir()),
    }


@mcp.tool()
async def get_login_status() -> dict[str, Any]:
    cfg = load_config()
    page = await open_url(cfg.wechat_mp.login_url)
    logged_in = await is_logged_in(page, cfg.wechat_mp.logged_in_indicators, cfg.wechat_mp.home_url_prefixes)
    return {"logged_in": logged_in, "profile_dir": str(get_profile_dir())}


@mcp.tool()
async def wait_for_login(timeout_ms: int = 120000, poll_ms: int = 1000) -> dict[str, Any]:
    cfg = load_config()
    page = await open_url(cfg.wechat_mp.login_url)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + (timeout_ms / 1000)
    while loop.time() < deadline:
        if await is_logged_in(page, cfg.wechat_mp.logged_in_indicators, cfg.wechat_mp.home_url_prefixes):
            return {"logged_in": True, "profile_dir": str(get_profile_dir())}
        await asyncio.sleep(poll_ms / 1000)
    return {"logged_in": False, "profile_dir": str(get_profile_dir())}


@mcp.tool()
async def monitor_login(
    ctx: Context,
    timeout_ms: int = 300000,
    poll_ms: int = 1000,
    url: str | None = None,
    headless: bool | None = None,
    slow_mo_ms: int | None = None,
    channel: str | None = None,
    executable_path: str | None = None,
    push_qr_on_change: bool = True,
) -> dict[str, Any]:
    cfg = load_config()
    target_url = url or cfg.wechat_mp.login_url
    print(f"[monitor_login] navigate url={target_url}")
    page = await open_url(
        target_url,
        headless=headless,
        slow_mo_ms=slow_mo_ms,
        channel=channel,
        executable_path=executable_path,
    )

    loop = asyncio.get_running_loop()
    deadline = loop.time() + (timeout_ms / 1000)
    last_stage: str | None = None
    last_qr: dict[str, Any] | None = None

    async def emit(stage: str, detail: str | None = None) -> None:
        try:
            msg = f"login_stage stage={stage}"
            if detail:
                msg += f" detail={detail}"
            if last_qr is not None and "sha256" in last_qr:
                msg += f" qr_sha256={last_qr.get('sha256')}"
            await ctx.info(msg)
        except Exception:
            pass

    while True:
        stage = await detect_login_stage(page, cfg.wechat_mp.logged_in_indicators, cfg.wechat_mp.home_url_prefixes)
        if stage.stage != last_stage:
            last_stage = stage.stage
            try:
                print(f"[monitor_login] stage={stage.stage} url={page.url}")
            except Exception:
                print(f"[monitor_login] stage={stage.stage}")
            last_qr = None
            if push_qr_on_change and stage.stage in ["await_scan", "qr_expired"]:
                try:
                    qr = await extract_qr_base64(page, cfg.wechat_mp.qr_selectors)
                    last_qr = {
                        "mime": qr.mime,
                        "base64": qr.base64_data,
                        "data_url": qr.data_url,
                        "selector": qr.selector,
                        "source_url": qr.source_url,
                        "file_path": qr.file_path,
                        "sha256": qr.sha256,
                        "bytes_len": qr.bytes_len,
                        "base64_len": qr.base64_len,
                    }
                except Exception:
                    last_qr = None
            await emit(stage.stage, stage.detail)

        if stage.stage == "logged_in":
            print("[monitor_login] login detected")
            return {
                "logged_in": True,
                "stage": stage.stage,
                "profile_dir": str(get_profile_dir()),
            }

        if loop.time() >= deadline:
            print("[monitor_login] timeout")
            return {
                "logged_in": False,
                "stage": stage.stage,
                "profile_dir": str(get_profile_dir()),
            }

        if ctx is not None:
            elapsed = (timeout_ms / 1000) - max(0.0, deadline - loop.time())
            await ctx.report_progress(elapsed, total=timeout_ms / 1000, message=stage.stage)

        if push_qr_on_change and stage.stage in ["await_scan", "qr_expired"] and last_qr is None:
            try:
                qr = await extract_qr_base64(page, cfg.wechat_mp.qr_selectors)
                last_qr = {
                    "mime": qr.mime,
                    "base64": qr.base64_data,
                    "data_url": qr.data_url,
                    "selector": qr.selector,
                    "source_url": qr.source_url,
                    "file_path": qr.file_path,
                    "sha256": qr.sha256,
                    "bytes_len": qr.bytes_len,
                    "base64_len": qr.base64_len,
                }
                await emit(stage.stage, stage.detail)
                print("[monitor_login] qr captured")
            except Exception:
                last_qr = None

        await asyncio.sleep(poll_ms / 1000)


@mcp.tool()
async def reset_login_state() -> dict[str, Any]:
    profile_dir = await reset_session()
    return {"ok": True, "profile_dir": str(profile_dir)}


@mcp.tool()
async def run_web_steps(
    draft_title: str | None = None,
    url: str | None = None,
    headless: bool | None = None,
    slow_mo_ms: int | None = None,
    channel: str | None = None,
    executable_path: str | None = None,
) -> dict[str, Any]:
    cfg = load_config()
    page = await open_url(
        url or cfg.wechat_mp.login_url,
        headless=headless,
        slow_mo_ms=slow_mo_ms,
        channel=channel,
        executable_path=executable_path,
    )
    if not await is_logged_in(page, cfg.wechat_mp.logged_in_indicators, cfg.wechat_mp.home_url_prefixes):
        return {"completed": False, "results": [], "error": "未登录，无法进入草稿箱", "page_url": page.url}

    results: list[dict[str, Any]] = []
    try:
        await page.get_by_text("内容管理", exact=False).first.click(timeout=30000)
        results.append({"index": 0, "action": "click_text", "ok": True, "detail": "内容管理"})
    except Exception as e:
        detail = str(e)
        results.append({"index": 0, "action": "click_text", "ok": False, "detail": detail})
        return {"completed": False, "results": results, "error": detail, "page_url": page.url}

    try:
        await page.get_by_text("草稿箱", exact=False).first.click(timeout=30000)
        results.append({"index": 1, "action": "click_text", "ok": True, "detail": "草稿箱"})
    except Exception as e:
        detail = str(e)
        results.append({"index": 1, "action": "click_text", "ok": False, "detail": detail})
        return {"completed": False, "results": results, "error": detail, "page_url": page.url}

    return {"completed": True, "results": results, "error": None, "page_url": page.url, "draft_title": draft_title}

