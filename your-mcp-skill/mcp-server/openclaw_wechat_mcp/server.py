from __future__ import annotations

import asyncio
from typing import Any
from datetime import datetime
import builtins
from pathlib import Path
import json

from mcp.server.fastmcp import Context, FastMCP
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .config import load_config, resolve_data_path
from .tools.browser import (
    detect_login_stage,
    extract_qr_base64,
    get_profile_dir,
    is_logged_in,
    get_current_page,
    open_url,
    reset_session,
 )
from .tools.api_publish import WeChatPublisher


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
async def wait_for_publish_success(
    draft_title: str | None = None,
    timeout_ms: int = 180000,
    poll_ms: int = 1000,
    headless: bool | None = None,
    slow_mo_ms: int | None = None,
    channel: str | None = None,
    executable_path: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    cfg = load_config()
    page = await get_current_page(
        headless=headless,
        slow_mo_ms=slow_mo_ms,
        channel=channel,
        executable_path=executable_path,
    )
    loop = asyncio.get_running_loop()
    deadline = loop.time() + (timeout_ms / 1000)

    async def _is_home() -> bool:
        try:
            for prefix in cfg.wechat_mp.home_url_prefixes:
                if page.url.startswith(prefix):
                    return True
        except Exception:
            return False
        return False

    async def _has_recent(title: str | None) -> bool:
        try:
            recent = page.get_by_text("近期发表", exact=False).first
            if not await recent.is_visible(timeout=200):
                return False
            if title:
                return await page.get_by_text(title, exact=False).first.is_visible(timeout=200)
            return True
        except Exception:
            return False

    while loop.time() < deadline:
        home = await _is_home()
        recent_ok = await _has_recent(draft_title) if home else False

        if home:
            return {
                "ok": True,
                "published": True,
                "url": page.url,
                "recent_section": await _has_recent(None),
                "matched_title": recent_ok,
                "draft_title": draft_title,
                "profile_dir": str(get_profile_dir()),
            }

        if ctx is not None:
            elapsed = (timeout_ms / 1000) - max(0.0, deadline - loop.time())
            await ctx.report_progress(elapsed, total=timeout_ms / 1000, message=page.url)

        await asyncio.sleep(poll_ms / 1000)

    return {
        "ok": False,
        "published": False,
        "url": page.url,
        "draft_title": draft_title,
        "profile_dir": str(get_profile_dir()),
    }


@mcp.tool()
async def publish_draft_from_draftbox(
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

    try:
        await page.get_by_text("草稿箱", exact=False).first.wait_for(state="visible", timeout=60000)
        try:
            await page.wait_for_load_state("networkidle", timeout=60000)
        except Exception:
            pass
    except Exception:
        pass

    try:
        container = None
        try:
            container_candidate = page.locator(".publish_card_container").first
            await container_candidate.wait_for(state="visible", timeout=60000)
            container = container_candidate
        except Exception:
            container = None
        try:
            seed_new = page.get_by_text("新的创作", exact=False).first
            await seed_new.wait_for(state="visible", timeout=30000)
        except Exception:
            pass

        if draft_title:
            seed = (
                (container or page)
                .locator(".weui-desktop-publish__cover__title")
                .get_by_text(draft_title, exact=False)
                .first
            )
            await seed.wait_for(state="visible", timeout=60000)
            scope = seed.locator("xpath=ancestor::div[contains(@class,'weui-desktop-card')][1]")
            results.append({"index": 2, "action": "find_draft", "ok": True, "detail": f"title={draft_title}"})
        else:
            cards = (container or page).locator(".weui-desktop-card:has(.publish_enable_button), .weui-desktop-card")
            count = await cards.count()
            if count > 0:
                scope = cards.first
                results.append({"index": 2, "action": "find_draft", "ok": True, "detail": f"most_recent count={count}"})
            else:
                btns = (container or page).locator(".publish_enable_button, button:has-text(\"发表\")")
                btn_count = await btns.count()
                if btn_count == 0:
                    # 尝试用纯文本匹配找到“发表”按钮并回溯到卡片
                    try:
                        any_pub = (container or page).get_by_text("发表", exact=False).first
                        await any_pub.wait_for(state="visible", timeout=30000)
                        scope = any_pub.locator("xpath=ancestor::div[contains(@class,'weui-desktop-card')][1]")
                    except Exception:
                        raise RuntimeError("未找到可发表的草稿卡片")
                else:
                    scope = btns.first.locator("xpath=ancestor::div[contains(@class,'weui-desktop-card')][1]")
                results.append(
                    {"index": 2, "action": "find_draft", "ok": True, "detail": f"most_recent_by_button count={btn_count}"}
                )

        await scope.wait_for(state="visible", timeout=60000)
        await scope.hover(timeout=30000)
        results.append({"index": 3, "action": "hover_card", "ok": True, "detail": None})
    except Exception as e:
        detail = str(e)
        results.append({"index": 2, "action": "find_draft", "ok": False, "detail": detail})
        return {"completed": False, "results": results, "error": detail, "page_url": page.url, "draft_title": draft_title}

    new_page = None
    try:
        publish_btn = scope.locator(".publish_enable_button").first.get_by_text("发表", exact=False).first
        await publish_btn.wait_for(state="visible", timeout=30000)
        try:
            async with page.context.expect_page(timeout=7000) as new_page_info:
                await publish_btn.click(timeout=30000)
            new_page = await new_page_info.value
        except PlaywrightTimeoutError:
            new_page = None
        results.append({"index": 4, "action": "click_publish", "ok": True, "detail": None})
    except Exception as e:
        detail = str(e)
        results.append({"index": 4, "action": "click_publish", "ok": False, "detail": detail})
        return {"completed": False, "results": results, "error": detail, "page_url": page.url, "draft_title": draft_title}

    try:
        target_prefix = "https://mp.weixin.qq.com/cgi-bin/appmsg"
        target_page = new_page or page

        for _ in range(60):
            if target_page.url.startswith(target_prefix):
                break
            await asyncio.sleep(0.5)

        if not target_page.url.startswith(target_prefix):
            try:
                pages = list(page.context.pages)
                for p in reversed(pages):
                    if p.url.startswith(target_prefix):
                        target_page = p
                        break
            except Exception:
                pass
            await asyncio.sleep(0.5)

        if not target_page.url.startswith(target_prefix):
            raise RuntimeError(f"未跳转到发表页面: {target_page.url}")

        try:
            await target_page.wait_for_load_state("domcontentloaded", timeout=60000)
        except Exception:
            pass
        await asyncio.sleep(1.0)

        results.append({"index": 5, "action": "wait_appmsg", "ok": True, "detail": target_page.url})

        async def _return_wechat_verify(step_index: int) -> dict[str, Any] | None:
            try:
                pages = list(page.context.pages)
            except Exception:
                pages = [target_page]

            verify_page = None
            for p in reversed(pages):
                try:
                    modal = (
                        p.locator(".weui-desktop-dialog__wrp, .weui-desktop-dialog, .dialog")
                        .filter(has_text="微信验证", visible=True)
                        .first
                    )
                    if await modal.is_visible(timeout=800):
                        verify_page = p
                        break
                except Exception:
                    continue

            if verify_page is None:
                return None

            try:
                selectors = [
                    '.dialog:has-text("微信验证") img.js_qrcode',
                    '.dialog:has-text("微信验证") img.qrcode',
                    '.dialog:has-text("微信验证") img[alt*="二维码"]',
                    '.dialog:has-text("微信验证") canvas',
                    ".dialog:visible img.js_qrcode",
                    ".dialog:visible img.qrcode",
                    ".dialog:visible canvas",
                    ".weui-desktop-dialog__wrp:visible img",
                    ".weui-desktop-dialog__wrp:visible canvas",
                    ".weui-desktop-dialog:visible img",
                    ".weui-desktop-dialog:visible canvas",
                ] + cfg.wechat_mp.qr_selectors
                qr = await extract_qr_base64(verify_page, selectors)
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
            except Exception as e:
                results.append({"index": step_index, "action": "wechat_verify", "ok": False, "detail": str(e)})
                return {
                    "completed": False,
                    "requires_user_action": True,
                    "user_action": "wechat_verify",
                    "qr": None,
                    "results": results,
                    "error": "需要微信扫码验证，但二维码提取失败",
                    "page_url": verify_page.url,
                    "draft_title": draft_title,
                }

            results.append({"index": step_index, "action": "wechat_verify", "ok": True, "detail": verify_page.url})
            return {
                "completed": False,
                "requires_user_action": True,
                "user_action": "wechat_verify",
                "qr": qr_payload,
                "results": results,
                "error": "需要微信扫码验证",
                "page_url": verify_page.url,
                "draft_title": draft_title,
            }

        maybe_verify = await _return_wechat_verify(4)
        if maybe_verify is not None:
            return maybe_verify

        maybe_verify = await _return_wechat_verify(5)
        if maybe_verify is not None:
            return maybe_verify

        try:
            no_need = target_page.get_by_role("button", name="无需声明并发表").first
            if await no_need.is_visible(timeout=1500):
                await no_need.click(timeout=30000)
                results.append({"index": 6, "action": "click_no_declare", "ok": True, "detail": "无需声明并发表"})
        except Exception:
            pass

        maybe_verify = await _return_wechat_verify(6)
        if maybe_verify is not None:
            return maybe_verify

        try:
            agree = target_page.get_by_role("button", name="同意以上声明").first
            if await agree.is_visible(timeout=1500):
                await agree.click(timeout=30000)
                results.append({"index": 6, "action": "click_agree_declare", "ok": True, "detail": "同意以上声明"})
        except Exception:
            pass

        maybe_verify = await _return_wechat_verify(6)
        if maybe_verify is not None:
            return maybe_verify

        try:
            async def _move_mouse_to(locator) -> None:
                try:
                    box = await locator.bounding_box()
                    if box:
                        await target_page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        return
                except Exception:
                    pass
                try:
                    await locator.hover(timeout=30000)
                except Exception:
                    pass

            async def _publish_button(scope):
                return scope.locator("button.weui-desktop-btn.weui-desktop-btn_primary:has-text(\"发表\")").first

            async def _wait_publish_visible(timeout_ms: int) -> None:
                btn = await _publish_button(target_page)
                await btn.wait_for(state="visible", timeout=timeout_ms)

            async def _click(locator, step_index: int, detail: str) -> None:
                await _move_mouse_to(locator)
                await asyncio.sleep(0.3)
                try:
                    await locator.click(timeout=30000)
                except Exception:
                    await locator.click(timeout=30000, force=True)
                results.append({"index": step_index, "action": "click_publish", "ok": True, "detail": detail})

            try:
                await _wait_publish_visible(60000)
            except Exception:
                maybe_verify = await _return_wechat_verify(7)
                if maybe_verify is not None:
                    return maybe_verify
                raise
            btn1 = await _publish_button(target_page)
            await _click(btn1, 7, "发表(first)")

            await asyncio.sleep(1.0)

            try:
                await target_page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass

            maybe_verify = await _return_wechat_verify(7)
            if maybe_verify is not None:
                return maybe_verify

            dialogs = target_page.locator(".weui-desktop-dialog__wrp:visible, .weui-desktop-dialog:visible")
            dialog_btn = dialogs.locator("button.weui-desktop-btn.weui-desktop-btn_primary:has-text(\"发表\")").first
            if await dialog_btn.is_visible(timeout=1000):
                await _click(dialog_btn, 8, "发表(confirm_dialog)")
            else:
                btn2 = await _publish_button(target_page)
                if await btn2.is_visible(timeout=1000):
                    await _click(btn2, 8, "发表(second)")

            await asyncio.sleep(1.0)
            maybe_verify = await _return_wechat_verify(8)
            if maybe_verify is not None:
                return maybe_verify
        except Exception as e:
            detail = str(e)
            results.append({"index": 7, "action": "click_publish", "ok": False, "detail": detail})
            return {
                "completed": False,
                "results": results,
                "error": detail,
                "page_url": target_page.url,
                "draft_title": draft_title,
            }
    except Exception as e:
        detail = str(e)
        results.append({"index": 5, "action": "wait_appmsg", "ok": False, "detail": detail})
        return {"completed": False, "results": results, "error": detail, "page_url": page.url, "draft_title": draft_title}

    return {"completed": True, "results": results, "error": None, "page_url": page.url, "draft_title": draft_title}



async def publish_article(
    ctx: Context,
    title: str,
    author: str,
    content: str,
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
    try:
        await page.get_by_text("草稿箱", exact=False).first.wait_for(state="visible", timeout=60000)
    except Exception:
        pass
    new_page = None
    try:
        seed = page.get_by_text("新的创作", exact=False).first
        try:
            await seed.wait_for(state="visible", timeout=60000)
        except Exception:
            pass
        try:
            await seed.hover(timeout=30000)
        except Exception:
            box = await seed.bounding_box()
            if box:
                await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        menu_item = page.get_by_text("写新文章", exact=False).first
        await menu_item.wait_for(state="visible", timeout=30000)
        async with page.context.expect_page(timeout=7000) as new_page_info:
            await menu_item.click(timeout=30000)
        new_page = await new_page_info.value
        results.append({"index": 2, "action": "new_article", "ok": True, "detail": "写新文章"})
    except Exception as e:
        detail = str(e)
        results.append({"index": 2, "action": "new_article", "ok": False, "detail": detail})
        return {"completed": False, "results": results, "error": detail, "page_url": page.url}
    try:
        target_prefix = "https://mp.weixin.qq.com/cgi-bin/appmsg"
        target_page = new_page or page
        for _ in range(60):
            if target_page.url.startswith(target_prefix):
                break
            await asyncio.sleep(0.5)
        if not target_page.url.startswith(target_prefix):
            try:
                pages = list(page.context.pages)
                for p in reversed(pages):
                    if p.url.startswith(target_prefix):
                        target_page = p
                        break
            except Exception:
                pass
            await asyncio.sleep(0.5)
        if not target_page.url.startswith(target_prefix):
            raise RuntimeError(f"未跳转到写新文章页面: {target_page.url}")
        try:
            await target_page.wait_for_load_state("domcontentloaded", timeout=60000)
        except Exception:
            pass
        await asyncio.sleep(1.0)
        results.append({"index": 3, "action": "wait_editor", "ok": True, "detail": target_page.url})
        def _maybe_decode_unicode(s: str) -> str:
            try:
                if "\\u" in s:
                    import codecs
                    return codecs.decode(s, "unicode_escape")
            except Exception:
                pass
            return s
        content = _maybe_decode_unicode(content)
        async def _fill(placeholders: list[str], text: str) -> bool:
            for p in placeholders:
                try:
                    loc = target_page.get_by_placeholder(p, exact=False).first
                    if await loc.is_visible(timeout=800):
                        await loc.fill(text)
                        return True
                except Exception:
                    continue
            try:
                loc = target_page.locator(
                    "input[placeholder*='{}'], textarea[placeholder*='{}'], [contenteditable='true'][data-placeholder*='{}']".format(
                        placeholders[0], placeholders[0], placeholders[0]
                    )
                ).first
                if await loc.is_visible(timeout=800):
                    await loc.fill(text)
                    return True
            except Exception:
                pass
            return False
        ok1 = await _fill(["请在这里输入标题", "请输入标题", "标题"], title)
        ok2 = await _fill(["请输入作者", "作者"], author)
        async def _find_editor() -> Any | None:
            # 1) 直接在页面查找
            cand = [
                target_page.get_by_placeholder("从这里开始写正文", exact=False).first,
                target_page.get_by_role("textbox").first,
                target_page.locator("[contenteditable='true']").first,
                target_page.locator("div[role='textbox']").first,
            ]
            for loc in cand:
                try:
                    if await loc.is_visible(timeout=800):
                        return loc
                except Exception:
                    continue
            # 2) 在所有 iframe 中查找
            try:
                frames = list(getattr(target_page, "frames", []))
            except Exception:
                frames = []
            for f in reversed(frames):
                for loc in [
                    f.get_by_placeholder("从这里开始写正文", exact=False).first,
                    f.get_by_role("textbox").first,
                    f.locator("[contenteditable='true']").first,
                    f.locator("div[role='textbox']").first,
                ]:
                    try:
                        if await loc.is_visible(timeout=800):
                            return loc
                    except Exception:
                        continue
            return None
        editor = await _find_editor()
        if editor is None:
            raise RuntimeError("正文编辑区域未找到")
        try:
            # 对多数富文本编辑器，fill 不生效，采用点击并插入文本
            await editor.click(timeout=30000)
            await asyncio.sleep(0.2)
            await target_page.keyboard.insert_text(content)
        except Exception:
            await editor.fill(content)
        results.append({"index": 4, "action": "fill_fields", "ok": True, "detail": None})
        try:
            cover = target_page.get_by_text("拖拽或选择封面", exact=False).first
            if await cover.is_visible(timeout=1500):
                try:
                    await cover.hover(timeout=30000)
                except Exception:
                    box = await cover.bounding_box()
                    if box:
                        await target_page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                btn = target_page.get_by_text("从正文选择", exact=False).first
                await btn.wait_for(state="visible", timeout=30000)
                await btn.click(timeout=30000)
                next_btn = target_page.get_by_role("button", name="下一步").first
                if await next_btn.is_visible(timeout=2000):
                    await next_btn.click(timeout=30000)
                ok_btn = target_page.get_by_role("button", name="确认").first
                if await ok_btn.is_visible(timeout=2000):
                    await ok_btn.click(timeout=30000)
                results.append({"index": 5, "action": "select_cover", "ok": True, "detail": "从正文选择"})
            else:
                results.append({"index": 5, "action": "select_cover", "ok": True, "detail": "skip"})
        except Exception as e:
            results.append({"index": 5, "action": "select_cover", "ok": False, "detail": str(e)})
        await asyncio.sleep(1.0)
        async def _return_wechat_verify(step_index: int) -> dict[str, Any] | None:
            try:
                pages = list(page.context.pages)
            except Exception:
                pages = [target_page]
            verify_page = None
            for p in reversed(pages):
                try:
                    modal = (
                        p.locator(".weui-desktop-dialog__wrp, .weui-desktop-dialog, .dialog")
                        .filter(has_text="微信验证", visible=True)
                        .first
                    )
                    if await modal.is_visible(timeout=800):
                        verify_page = p
                        break
                except Exception:
                    continue
            if verify_page is None:
                return None
            try:
                selectors = [
                    '.dialog:has-text("微信验证") img.js_qrcode',
                    '.dialog:has-text("微信验证") img.qrcode',
                    '.dialog:has-text("微信验证") img[alt*="二维码"]',
                    '.dialog:has-text("微信验证") canvas',
                    ".dialog:visible img.js_qrcode",
                    ".dialog:visible img.qrcode",
                    ".dialog:visible canvas",
                    ".weui-desktop-dialog__wrp:visible img",
                    ".weui-desktop-dialog__wrp:visible canvas",
                    ".weui-desktop-dialog:visible img",
                    ".weui-desktop-dialog:visible canvas",
                ] + cfg.wechat_mp.qr_selectors
                qr = await extract_qr_base64(verify_page, selectors)
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
            except Exception as e:
                results.append({"index": step_index, "action": "wechat_verify", "ok": False, "detail": str(e)})
                return {
                    "completed": False,
                    "requires_user_action": True,
                    "user_action": "wechat_verify",
                    "qr": None,
                    "results": results,
                    "error": "需要微信扫码验证，但二维码提取失败",
                    "page_url": verify_page.url,
                    "article_title": title,
                }
            results.append({"index": step_index, "action": "wechat_verify", "ok": True, "detail": "qr"})
            return {
                "completed": False,
                "requires_user_action": True,
                "user_action": "wechat_verify",
                "qr": qr_payload,
                "results": results,
                "error": None,
                "page_url": verify_page.url,
                "article_title": title,
            }
        async def _move_mouse_to(locator) -> None:
            try:
                box = await locator.bounding_box()
                if box:
                    await target_page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    return
            except Exception:
                pass
            try:
                await locator.hover(timeout=30000)
            except Exception:
                pass
        async def _publish_button(scope):
            return scope.locator("button.weui-desktop-btn.weui-desktop-btn_primary:has-text(\"发表\")").first
        async def _wait_publish_visible(timeout_ms: int) -> None:
            btn = await _publish_button(target_page)
            await btn.wait_for(state="visible", timeout=timeout_ms)
        async def _click(locator, step_index: int, detail: str) -> None:
            await _move_mouse_to(locator)
            await asyncio.sleep(0.3)
            try:
                await locator.click(timeout=30000)
            except Exception:
                await locator.click(timeout=30000, force=True)
            results.append({"index": step_index, "action": "click_publish", "ok": True, "detail": detail})
        try:
            try:
                await _wait_publish_visible(60000)
            except Exception:
                maybe_verify = await _return_wechat_verify(6)
                if maybe_verify is not None:
                    return maybe_verify
                raise
            btn1 = await _publish_button(target_page)
            await _click(btn1, 6, "发表(first)")
            await asyncio.sleep(1.0)
            try:
                await target_page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            maybe_verify = await _return_wechat_verify(6)
            if maybe_verify is not None:
                return maybe_verify
            dialogs = target_page.locator(".weui-desktop-dialog__wrp:visible, .weui-desktop-dialog:visible")
            dialog_btn = dialogs.locator("button.weui-desktop-btn.weui-desktop-btn_primary:has-text(\"发表\")").first
            if await dialog_btn.is_visible(timeout=1000):
                await _click(dialog_btn, 7, "发表(confirm_dialog)")
            else:
                btn2 = await _publish_button(target_page)
                if await btn2.is_visible(timeout=1000):
                    await _click(btn2, 7, "发表(second)")
            await asyncio.sleep(1.0)
            maybe_verify = await _return_wechat_verify(7)
            if maybe_verify is not None:
                return maybe_verify
        except Exception as e:
            detail = str(e)
            results.append({"index": 6, "action": "click_publish", "ok": False, "detail": detail})
            return {"completed": False, "results": results, "error": detail, "page_url": target_page.url, "article_title": title}
    except Exception as e:
        detail = str(e)
        results.append({"index": 3, "action": "wait_editor", "ok": False, "detail": detail})
        return {"completed": False, "results": results, "error": detail, "page_url": page.url}
    poll = await wait_for_publish_success(draft_title=title, ctx=ctx)
    return {
        "completed": True,
        "results": results,
        "error": None,
        "page_url": page.url,
        "article_title": title,
        "publish_result": poll,
    }

@mcp.tool()
async def publish_draft_api(
    ctx: Context,
    title: str,
    content: str,
    cover_path: str,
    author: str | None = "",
    digest: str | None = None,
    appid: str | None = None,
    appsecret: str | None = None,
) -> dict[str, Any]:
    cfg = load_config()
    use_appid = appid or getattr(cfg.wechat_mp, "appid", None)
    use_secret = appsecret or getattr(cfg.wechat_mp, "appsecret", None)
    if not use_appid or not use_secret:
        sc = {"ok": False, "error": "缺少appid或appsecret", "results": [], "media_id": None}
        return {
            "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
            "structuredContent": sc,
            "isError": False,
        }
    results: list[dict[str, Any]] = []
    try:
        def _maybe_decode_unicode(s: str) -> str:
            try:
                if "\\u" in s:
                    import codecs
                    return codecs.decode(s, "unicode_escape")
            except Exception:
                pass
            return s
        title = _maybe_decode_unicode(title)
        author = _maybe_decode_unicode(author or "")
        content = _maybe_decode_unicode(content)
        digest = _maybe_decode_unicode(digest or "")
        # 校验封面路径
        if not cover_path or not Path(cover_path).is_file():
            sc = {"ok": False, "error": "封面路径无效或文件不存在", "results": [], "media_id": None}
            return {
                "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
                "structuredContent": sc,
                "isError": False,
            }
        pub = WeChatPublisher(use_appid, use_secret)
        token = pub.ensure_valid_token()
        results.append({"index": 0, "action": "get_token", "ok": True})
        thumb_media_id = pub.upload_image(cover_path)
        results.append({"index": 1, "action": "upload_image", "ok": True})
        media_id = pub.add_draft(title=title, content=content, author=author or "", thumb_media_id=thumb_media_id, digest=digest or "" )
        results.append({"index": 2, "action": "add_draft", "ok": True})
        try:
            await ctx.info(f"draft_created media_id={media_id}")
        except Exception:
            pass
        sc = {"ok": True, "error": None, "results": results, "media_id": media_id}
        return {
            "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
            "structuredContent": sc,
            "isError": False,
        }
    except Exception as e:
        detail = str(e)
        results.append({"index": len(results), "action": "error", "ok": False, "detail": detail})
        try:
            await ctx.error(f"publish_draft_api_error {detail}")
        except Exception:
            pass
        sc = {"ok": False, "error": detail, "results": results, "media_id": None}
        return {
            "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
            "structuredContent": sc,
            "isError": False,
        }

@mcp.tool()
async def create_draft_then_publish(
    ctx: Context,
    title: str,
    content: str,
    cover_path: str,
    author: str | None = "",
    digest: str | None = None,
    headless: bool | None = None,
    slow_mo_ms: int | None = None,
    channel: str | None = None,
    executable_path: str | None = None,
    appid: str | None = None,
    appsecret: str | None = None,
) -> dict[str, Any]:
    cfg = load_config()
    use_appid = appid or getattr(cfg.wechat_mp, "appid", None)
    use_secret = appsecret or getattr(cfg.wechat_mp, "appsecret", None)
    if not use_appid or not use_secret:
        sc = {"ok": False, "error": "缺少appid或appsecret", "results": [], "media_id": None}
        return {
            "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
            "structuredContent": sc,
            "isError": False,
        }
    steps: list[dict[str, Any]] = []
    try:
        def _maybe_decode_unicode(s: str) -> str:
            try:
                if "\\u" in s:
                    import codecs
                    return codecs.decode(s, "unicode_escape")
            except Exception:
                pass
            return s
        title = _maybe_decode_unicode(title)
        author = _maybe_decode_unicode(author or "")
        content = _maybe_decode_unicode(content)
        digest = _maybe_decode_unicode(digest or "")
        # 校验封面路径
        if not cover_path or not Path(cover_path).is_file():
            sc = {"ok": False, "error": "封面路径无效或文件不存在", "results": [], "media_id": None}
            return {
                "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
                "structuredContent": sc,
                "isError": False,
            }
        pub = WeChatPublisher(use_appid, use_secret)
        token = pub.ensure_valid_token()
        steps.append({"index": 0, "action": "get_token", "ok": True})
        thumb_media_id = pub.upload_image(cover_path)
        steps.append({"index": 1, "action": "upload_image", "ok": True})
        media_id = pub.add_draft(
            title=title, content=content, author=author or "", thumb_media_id=thumb_media_id, digest=digest or ""
        )
        steps.append({"index": 2, "action": "add_draft", "ok": True, "media_id": media_id})
        try:
            await ctx.info(f"draft_created media_id={media_id}")
        except Exception:
            pass
    except Exception as e:
        detail = str(e)
        steps.append({"index": len(steps), "action": "error", "ok": False, "detail": detail})
        try:
            await ctx.error(f"create_draft_error {detail}")
        except Exception:
            pass
        sc = {"ok": False, "error": detail, "results": steps, "media_id": None}
        return {
            "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
            "structuredContent": sc,
            "isError": False,
        }

    try:
        pub_result = await publish_draft_from_draftbox(
            draft_title=title,
            url=cfg.wechat_mp.login_url,
            headless=headless,
            slow_mo_ms=slow_mo_ms,
            channel=channel,
            executable_path=executable_path,
        )
        steps.append({"index": 3, "action": "publish_draft_from_draftbox", "ok": pub_result.get("completed", False)})
        if pub_result.get("requires_user_action"):
            sc = {
                "ok": False,
                "requires_user_action": True,
                "user_action": pub_result.get("user_action"),
                "qr": pub_result.get("qr"),
                "results": steps + pub_result.get("results", []),
                "media_id": media_id,
            }
            return {
                "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
                "structuredContent": sc,
                "isError": False,
            }
        if not pub_result.get("completed"):
            sc = {"ok": False, "error": pub_result.get("error"), "results": steps + pub_result.get("results", [])}
            return {
                "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
                "structuredContent": sc,
                "isError": False,
            }
    except Exception as e:
        detail = str(e)
        steps.append({"index": 3, "action": "publish_draft_from_draftbox", "ok": False, "detail": detail})
        sc = {"ok": False, "error": detail, "results": steps}
        return {
            "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
            "structuredContent": sc,
            "isError": False,
        }

    poll = await wait_for_publish_success(draft_title=title, ctx=ctx)
    steps.append({"index": 4, "action": "wait_for_publish_success", "ok": poll.get("ok", False)})
    sc = {
        "ok": poll.get("ok", False),
        "published": poll.get("published", False),
        "url": poll.get("url"),
        "results": steps,
        "media_id": media_id,
        "profile_dir": poll.get("profile_dir"),
        "matched_title": poll.get("matched_title"),
    }
    return {
        "content": [{"type": "text", "text": json.dumps(sc, ensure_ascii=False, indent=2)}],
        "structuredContent": sc,
        "isError": False,
    }
