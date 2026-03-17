from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


WebStepAction = Literal[
    "click_css",
    "click_text",
    "wait_for_css",
    "wait_for_text",
    "wait_for_url",
    "sleep",
    "evaluate",
]


class WebStep(BaseModel):
    action: WebStepAction
    selector: str | None = None
    text: str | None = None
    url: str | None = None
    timeout_ms: int | None = None
    sleep_ms: int | None = None
    script: str | None = None


class WebStepResult(BaseModel):
    index: int
    action: WebStepAction
    ok: bool
    detail: str | None = None


class RunWebStepsResponse(BaseModel):
    completed: bool
    results: list[WebStepResult] = Field(default_factory=list)
    error: str | None = None

