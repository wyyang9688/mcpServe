from pathlib import Path

from openclaw_wechat_mcp.config import load_config


def test_load_config_from_path(tmp_path: Path) -> None:
    cfg_path = tmp_path / "default.json"
    cfg_path.write_text(
        """
        {
          "browser": { "type": "chromium", "headless": true },
          "session": { "profile_dir": "data/profile" },
          "wechat_mp": { "login_url": "https://example.com/", "qr_selectors": ["img"], "logged_in_indicators": ["text=ok"] }
        }
        """,
        encoding="utf-8",
    )
    cfg = load_config(str(cfg_path))
    assert cfg.wechat_mp.login_url == "https://example.com/"

