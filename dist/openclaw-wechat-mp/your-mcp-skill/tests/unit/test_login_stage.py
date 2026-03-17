import asyncio

from openclaw_wechat_mcp.tools.browser import detect_login_stage


class _FakeLocator:
    def __init__(self, selector: str, page):
        self._selector = selector
        self._page = page
        self.first = self

    async def inner_text(self, timeout: int | None = None):
        if self._selector == "body":
            return self._page.body_text
        return ""

    async def is_visible(self, timeout: int | None = None):
        return self._selector in self._page.visible_selectors


class _FakePage:
    def __init__(self, body_text: str = "", visible_selectors: set[str] | None = None):
        self.body_text = body_text
        self.visible_selectors = visible_selectors or set()

    def locator(self, selector: str):
        return _FakeLocator(selector, self)


def test_detect_login_stage_logged_in():
    page = _FakePage(visible_selectors={"text=公众号平台"})
    stage = asyncio.run(detect_login_stage(page, ["text=公众号平台"]))
    assert stage.stage == "logged_in"


def test_detect_login_stage_logged_in_by_url():
    page = _FakePage()
    page.url = "https://mp.weixin.qq.com/cgi-bin/home?t=home/index"
    stage = asyncio.run(detect_login_stage(page, ["text=公众号平台"], ["https://mp.weixin.qq.com/cgi-bin/home"]))
    assert stage.stage == "logged_in"


def test_detect_login_stage_scanned_pending():
    page = _FakePage(body_text="扫码成功，请在手机上确认")
    stage = asyncio.run(detect_login_stage(page, ["text=公众号平台"]))
    assert stage.stage == "scanned_pending_confirm"


def test_detect_login_stage_expired():
    page = _FakePage(body_text="二维码已失效，点击刷新二维码")
    stage = asyncio.run(detect_login_stage(page, ["text=公众号平台"]))
    assert stage.stage == "qr_expired"


def test_detect_login_stage_await_scan_default():
    page = _FakePage(body_text="请使用微信扫码登录")
    stage = asyncio.run(detect_login_stage(page, ["text=公众号平台"]))
    assert stage.stage == "await_scan"

