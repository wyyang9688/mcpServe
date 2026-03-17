import asyncio

from openclaw_wechat_mcp.tools.workflow import run_steps
from openclaw_wechat_mcp.types.mcp_types import WebStep


class _FakeLocator:
    def __init__(self, page, kind: str, value: str):
        self._page = page
        self._kind = kind
        self._value = value
        self.first = self

    async def click(self, timeout: int | None = None):
        self._page.calls.append(("click", self._kind, self._value, timeout))

    async def wait_for(self, state: str = "visible", timeout: int | None = None):
        self._page.calls.append(("wait_for", self._kind, self._value, state, timeout))


class _FakePage:
    def __init__(self):
        self.calls = []

    def locator(self, selector: str):
        self.calls.append(("locator", selector))
        return _FakeLocator(self, "css", selector)

    def get_by_text(self, text: str, exact: bool = False):
        self.calls.append(("get_by_text", text, exact))
        return _FakeLocator(self, "text", text)

    async def wait_for_url(self, url: str, timeout: int | None = None):
        self.calls.append(("wait_for_url", url, timeout))

    async def evaluate(self, script: str):
        self.calls.append(("evaluate", script))


def test_run_steps_happy_path():
    page = _FakePage()
    steps = [
        WebStep(action="click_css", selector="#a"),
        WebStep(action="wait_for_text", text="ok", timeout_ms=123),
        WebStep(action="sleep", sleep_ms=1),
        WebStep(action="evaluate", script="1+1"),
    ]

    resp = asyncio.run(run_steps(page, steps))
    assert resp.completed is True
    assert any(c[0] == "click" for c in page.calls)


def test_run_steps_validation_error_stops():
    page = _FakePage()
    steps = [WebStep(action="click_css")]

    resp = asyncio.run(run_steps(page, steps))
    assert resp.completed is False
    assert resp.error

