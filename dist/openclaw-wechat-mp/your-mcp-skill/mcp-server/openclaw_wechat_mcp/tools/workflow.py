from __future__ import annotations

import asyncio

from playwright.async_api import Page

from ..types.mcp_types import RunWebStepsResponse, WebStep, WebStepResult


async def run_steps(page: Page, steps: list[WebStep]) -> RunWebStepsResponse:
    results: list[WebStepResult] = []
    for i, step in enumerate(steps):
        timeout = step.timeout_ms or 30000
        try:
            if step.action == "click_css":
                if not step.selector:
                    raise ValueError("selector is required for click_css")
                await page.locator(step.selector).first.click(timeout=timeout)

            elif step.action == "click_text":
                if not step.text:
                    raise ValueError("text is required for click_text")
                await page.get_by_text(step.text, exact=False).first.click(timeout=timeout)

            elif step.action == "wait_for_css":
                if not step.selector:
                    raise ValueError("selector is required for wait_for_css")
                await page.locator(step.selector).first.wait_for(state="visible", timeout=timeout)

            elif step.action == "wait_for_text":
                if not step.text:
                    raise ValueError("text is required for wait_for_text")
                await page.get_by_text(step.text, exact=False).first.wait_for(state="visible", timeout=timeout)

            elif step.action == "wait_for_url":
                if not step.url:
                    raise ValueError("url is required for wait_for_url")
                await page.wait_for_url(step.url, timeout=timeout)

            elif step.action == "sleep":
                sleep_ms = step.sleep_ms if step.sleep_ms is not None else 1000
                await asyncio.sleep(sleep_ms / 1000)

            elif step.action == "evaluate":
                if not step.script:
                    raise ValueError("script is required for evaluate")
                await page.evaluate(step.script)

            else:
                raise ValueError(f"unsupported action: {step.action}")

            results.append(WebStepResult(index=i, action=step.action, ok=True))
        except Exception as e:
            detail = str(e)
            results.append(WebStepResult(index=i, action=step.action, ok=False, detail=detail))
            return RunWebStepsResponse(completed=False, results=results, error=detail)

    return RunWebStepsResponse(completed=True, results=results)

