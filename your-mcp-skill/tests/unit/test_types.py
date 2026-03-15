import pytest

from openclaw_wechat_mcp.types.mcp_types import WebStep


def test_webstep_requires_fields() -> None:
    step = WebStep(action="click_css", selector="#btn")
    assert step.selector == "#btn"


def test_webstep_invalid_action() -> None:
    with pytest.raises(Exception):
        WebStep.model_validate({"action": "nope"})

