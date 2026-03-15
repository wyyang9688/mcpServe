from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from .config import load_config
from .tools.browser import (
    detect_login_stage,
    extract_qr_base64,
    get_profile_dir,
    is_logged_in,
    open_url,
    reset_session,
 )
from .tools.workflow import run_steps
from .types.mcp_types import WebStep


mcp = FastMCP("openclaw-wechat-mp-mcp")


@mcp.tool()
async def open_login_page(
    url: str | None = None,
    return_qr: bool = True,
    headless: bool | None = None,
    slow_mo_ms: int | None = None,
    channel: str | None = None,
    executable_path: str | None = None,
) -> dict[str, Any]:
    cfg = load_config()
    target_url = url or cfg.wechat_mp.login_url
    page = await open_url(
        target_url,
        headless=headless,
        slow_mo_ms=slow_mo_ms,
        channel=channel,
        executable_path=executable_path,
    )
    logged_in = await is_logged_in(page, cfg.wechat_mp.logged_in_indicators)
    qr_payload: dict[str, Any] | None = None
    if return_qr and not logged_in:
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
        except Exception:
            qr_payload = None
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
    logged_in = await is_logged_in(page, cfg.wechat_mp.logged_in_indicators)
    return {"logged_in": logged_in, "profile_dir": str(get_profile_dir())}


@mcp.tool()
async def wait_for_login(timeout_ms: int = 120000, poll_ms: int = 1000) -> dict[str, Any]:
    cfg = load_config()
    page = await open_url(cfg.wechat_mp.login_url)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + (timeout_ms / 1000)
    while loop.time() < deadline:
        if await is_logged_in(page, cfg.wechat_mp.logged_in_indicators):
            return {"logged_in": True, "profile_dir": str(get_profile_dir())}
        await asyncio.sleep(poll_ms / 1000)
    return {"logged_in": False, "profile_dir": str(get_profile_dir())}


@mcp.tool()
async def monitor_login(
    timeout_ms: int = 300000,
    poll_ms: int = 1000,
    url: str | None = None,
    headless: bool | None = None,
    slow_mo_ms: int | None = None,
    channel: str | None = None,
    executable_path: str | None = None,
    push_qr_on_change: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    cfg = load_config()
    target_url = url or cfg.wechat_mp.login_url
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
        if ctx is None:
            return
        payload: dict[str, Any] = {"stage": stage}
        if detail:
            payload["detail"] = detail
        if last_qr is not None:
            payload["qr"] = last_qr
        await ctx.info("login_stage", **payload)

    while True:
        stage = await detect_login_stage(page, cfg.wechat_mp.logged_in_indicators)
        if stage.stage != last_stage:
            last_stage = stage.stage
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
            return {
                "logged_in": True,
                "stage": stage.stage,
                "profile_dir": str(get_profile_dir()),
            }

        if loop.time() >= deadline:
            return {
                "logged_in": False,
                "stage": stage.stage,
                "profile_dir": str(get_profile_dir()),
            }

        if ctx is not None:
            elapsed = (timeout_ms / 1000) - max(0.0, deadline - loop.time())
            await ctx.report_progress(elapsed, total=timeout_ms / 1000, message=stage.stage)

        await asyncio.sleep(poll_ms / 1000)


@mcp.tool()
async def reset_login_state() -> dict[str, Any]:
    profile_dir = await reset_session()
    return {"ok": True, "profile_dir": str(profile_dir)}


@mcp.tool()
async def run_web_steps(steps: list[dict[str, Any]], url: str | None = None) -> dict[str, Any]:
    cfg = load_config()
    page = await open_url(url or cfg.wechat_mp.login_url)
    parsed_steps = [WebStep.model_validate(s) for s in steps]
    resp = await run_steps(page, parsed_steps)
    return resp.model_dump()

