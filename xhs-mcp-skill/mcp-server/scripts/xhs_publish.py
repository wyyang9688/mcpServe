#!/usr/bin/env python3
"""
CDP-based Xiaohongshu publisher.

Connects to a Chrome instance via Chrome DevTools Protocol to automate
publishing articles on Xiaohongshu (RED) creator center.
"""

import json
import os
import time
import sys
from typing import Any

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import requests
import websockets.sync.client as ws_client

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222

XHS_CREATOR_URL = "https://creator.xiaohongshu.com/publish/publish"
XHS_HOME_URL = "https://www.xiaohongshu.com"
XHS_LOGIN_CHECK_URL = "https://creator.xiaohongshu.com"

SELECTORS = {
    "image_text_tab": "div.creator-tab",
    "image_text_tab_text": "上传图文",
    "upload_input": "input.upload-input",
    "upload_input_alt": 'input[type="file"]',
    "title_input": 'input[placeholder*="填写标题"]',
    "title_input_alt": "input.d-text",
    "content_editor": "div.tiptap.ProseMirror",
    "content_editor_alt": 'div.ProseMirror[contenteditable="true"]',
    "publish_button_text": "发布",
    "login_indicator": '.user-info, .creator-header, [class*="user"]',
    "long_article_tab_text": "写长文",
    "new_creation_btn_text": "新的创作",
    "long_title_input": 'textarea.d-text[placeholder="输入标题"]',
    "auto_format_btn_text": "一键排版",
    "next_step_btn_text": "下一步",
    "template_card": ".template-card",
}

PAGE_LOAD_WAIT = 3
TAB_CLICK_WAIT = 2
UPLOAD_WAIT = 6
ACTION_INTERVAL = 1
AUTO_FORMAT_WAIT = 5
TEMPLATE_WAIT = 10


class CDPError(Exception):
    pass


class XiaohongshuPublisher:
    def __init__(self, host: str = CDP_HOST, port: int = CDP_PORT):
        self.host = host
        self.port = port
        self.ws = None
        self._msg_id = 0

    def _get_targets(self) -> list[dict]:
        url = f"http://{self.host}:{self.port}/json"
        for attempt in range(2):
            try:
                resp = requests.get(url, timeout=5)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                if attempt == 0:
                    from chrome_launcher import ensure_chrome
                    ensure_chrome(self.port)
                    time.sleep(2)
                else:
                    raise CDPError(f"Cannot reach Chrome on {self.host}:{self.port}: {e}")

    def _find_or_create_tab(self, target_url_prefix: str = "") -> str:
        targets = self._get_targets()
        pages = [t for t in targets if t.get("type") == "page"]
        if target_url_prefix:
            for t in pages:
                if t.get("url", "").startswith(target_url_prefix):
                    return t["webSocketDebuggerUrl"]
        resp = requests.put(
            f"http://{self.host}:{self.port}/json/new?{XHS_CREATOR_URL}",
            timeout=5,
        )
        if resp.ok:
            return resp.json().get("webSocketDebuggerUrl", "")
        if pages:
            return pages[0]["webSocketDebuggerUrl"]
        raise CDPError("No browser tabs available.")

    def connect(self, target_url_prefix: str = ""):
        ws_url = self._find_or_create_tab(target_url_prefix)
        if not ws_url:
            raise CDPError("Could not obtain WebSocket URL for any tab.")
        print(f"[cdp_publish] Connecting to {ws_url}")
        self.ws = ws_client.connect(ws_url)
        print("[cdp_publish] Connected to Chrome tab.")

    def disconnect(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    def _send(self, method: str, params: dict | None = None) -> dict:
        if not self.ws:
            raise CDPError("Not connected. Call connect() first.")
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))
        while True:
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == self._msg_id:
                if "error" in data:
                    raise CDPError(f"CDP error: {data['error']}")
                return data.get("result", {})

    def _evaluate(self, expression: str) -> Any:
        result = self._send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        remote_obj = result.get("result", {})
        if remote_obj.get("subtype") == "error":
            raise CDPError(f"JS error: {remote_obj.get('description', remote_obj)}")
        return remote_obj.get("value")

    def _navigate(self, url: str):
        print(f"[cdp_publish] Navigating to {url}")
        self._send("Page.enable")
        self._send("Page.navigate", {"url": url})
        time.sleep(PAGE_LOAD_WAIT)

    def check_login(self) -> bool:
        self._navigate(XHS_LOGIN_CHECK_URL)
        time.sleep(2)
        current_url = self._evaluate("window.location.href")
        print(f"[cdp_publish] Current URL: {current_url}")
        if "login" in current_url.lower():
            print("\n[cdp_publish] NOT LOGGED IN.\n  Please scan the QR code in the Chrome window to log in,\n  then run this script again.\n")
            return False
        print("[cdp_publish] Login confirmed.")
        return True

    def open_login_page(self):
        self._navigate(XHS_LOGIN_CHECK_URL)
        time.sleep(2)
        current_url = self._evaluate("window.location.href")
        if "login" not in current_url.lower():
            self._navigate("https://creator.xiaohongshu.com/login")
            time.sleep(2)
        print("\n[cdp_publish] Login page is open.\n  Please scan the QR code in the Chrome window to log in.\n")

    def _click_image_text_tab(self):
        print("[cdp_publish] Clicking '上传图文' tab...")
        tab_text = SELECTORS["image_text_tab_text"]
        selector = SELECTORS["image_text_tab"]
        clicked = self._evaluate(f"""
            (function() {{
                var tabs = document.querySelectorAll('{selector}');
                for (var i = 0; i < tabs.length; i++) {{
                    if (tabs[i].textContent.trim() === '{tab_text}') {{
                        tabs[i].click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if not clicked:
            raise CDPError(f"Could not find '{tab_text}' tab.")
        print("[cdp_publish] Tab clicked, waiting for upload area...")
        time.sleep(TAB_CLICK_WAIT)

    def _upload_images(self, image_paths: list[str]):
        if not image_paths:
            print("[cdp_publish] No images to upload, skipping.")
            return
        normalized = [p.replace("\\", "/") for p in image_paths]
        print(f"[cdp_publish] Uploading {len(image_paths)} image(s)...")
        self._send("DOM.enable")
        doc = self._send("DOM.getDocument")
        root_id = doc["root"]["nodeId"]
        node_id = 0
        for selector in (SELECTORS["upload_input"], SELECTORS["upload_input_alt"]):
            result = self._send("DOM.querySelector", {"nodeId": root_id, "selector": selector})
            node_id = result.get("nodeId", 0)
            if node_id:
                break
        if not node_id:
            raise CDPError("Could not find file input element.")
        self._send("DOM.setFileInputFiles", {"nodeId": node_id, "files": normalized})
        print("[cdp_publish] Images uploaded. Waiting for editor to appear...")
        time.sleep(UPLOAD_WAIT)

    def _fill_title(self, title: str):
        print(f"[cdp_publish] Setting title: {title[:40]}...")
        time.sleep(ACTION_INTERVAL)
        for selector in (SELECTORS["title_input"], SELECTORS["title_input_alt"]):
            found = self._evaluate(f"!!document.querySelector('{selector}')")
            if found:
                escaped_title = json.dumps(title)
                self._evaluate(f"""
                    (function() {{
                        var el = document.querySelector('{selector}');
                        var nativeSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ).set;
                        el.focus();
                        nativeSetter.call(el, {escaped_title});
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }})();
                """)
                print("[cdp_publish] Title set.")
                return
        raise CDPError("Could not find title input element.")

    def _fill_content(self, content: str):
        print(f"[cdp_publish] Setting content ({len(content)} chars)...")
        time.sleep(ACTION_INTERVAL)
        for selector in (SELECTORS["content_editor"], SELECTORS["content_editor_alt"]):
            found = self._evaluate(f"!!document.querySelector('{selector}')")
            if found:
                escaped = json.dumps(content)
                self._evaluate(f"""
                    (function() {{
                        var el = document.querySelector('{selector}');
                        el.focus();
                        var text = {escaped};
                        var paragraphs = text.split('\\n').filter(function(p) {{ return p.trim(); }});
                        var html = [];
                        for (var i = 0; i < paragraphs.length; i++) {{
                            html.push('<p>' + paragraphs[i] + '</p>');
                            if (i < paragraphs.length - 1) {{
                                html.push('<p><br></p>');
                            }}
                        }}
                        el.innerHTML = html.join('');
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }})();
                """)
                print("[cdp_publish] Content set.")
                return
        raise CDPError("Could not find content editor element.")

    def _click_publish(self):
        print("[cdp_publish] Clicking publish button...")
        time.sleep(ACTION_INTERVAL)
        btn_text = SELECTORS["publish_button_text"]
        clicked = self._evaluate(f"""
            (function() {{
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {{
                    var t = buttons[i].textContent.trim();
                    if (t === '{btn_text}') {{
                        buttons[i].click();
                        return true;
                    }}
                }}
                var spans = document.querySelectorAll('.d-button-content .d-text, .d-button-content span');
                for (var i = 0; i < spans.length; i++) {{
                    if (spans[i].textContent.trim() === '{btn_text}') {{
                        var el = spans[i].closest('button, [role="button"], .d-button, [class*="btn"], [class*="button"]');
                        if (!el) el = spans[i].closest('.d-button-content');
                        if (!el) el = spans[i];
                        el.click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if clicked:
            print("[cdp_publish] Publish button clicked.")
        else:
            raise CDPError("Could not find publish button.")

    def reply_comment(self, note_url: str, text: str):
        if not self.ws:
            raise CDPError("Not connected. Call connect() first.")
        self._navigate(note_url)
        time.sleep(2)
        self._send("DOM.enable")
        doc = self._send("DOM.getDocument")
        root_id = doc["root"]["nodeId"]
        filled = False
        for selector in (
            'textarea[placeholder*="评论"]',
            'textarea[placeholder*="写下"]',
            'textarea',
            '[contenteditable="true"]',
        ):
            found = self._evaluate(f"!!document.querySelector('{selector}')")
            if found:
                escaped = json.dumps(text)
                self._evaluate(f"""
                    (function() {{
                        var el = document.querySelector('{selector}');
                        if (!el) return false;
                        if (el.tagName && el.tagName.toLowerCase() === 'textarea') {{
                            var setter = Object.getOwnPropertyDescriptor(
                                window.HTMLTextAreaElement.prototype, 'value'
                            ).set;
                            el.focus();
                            setter.call(el, {escaped});
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            return true;
                        }} else {{
                            el.focus();
                            el.innerHTML = {escaped}.replace(/\\n/g, '<br>');
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            return true;
                        }}
                    }})();
                """)
                filled = True
                break
        if not filled:
            raise CDPError("Could not find comment input.")
        time.sleep(ACTION_INTERVAL)
        labels = ["发布", "评论", "发送", "提交"]
        clicked = False
        for lbl in labels:
            res = self._evaluate(f"""
                (function() {{
                    var buttons = document.querySelectorAll('button, [role="button"], .d-button, [class*="btn"]');
                    for (var i = 0; i < buttons.length; i++) {{
                        var t = buttons[i].textContent.trim();
                        if (t === '{lbl}') {{
                            buttons[i].click();
                            return true;
                        }}
                    }}
                    var spans = document.querySelectorAll('.d-button-content .d-text, .d-button-content span');
                    for (var j = 0; j < spans.length; j++) {{
                        if (spans[j].textContent.trim() === '{lbl}') {{
                            var el = spans[j].closest('button, [role="button"], .d-button, [class*="btn"]');
                            if (!el) el = spans[j];
                            el.click();
                            return true;
                        }}
                    }}
                    return false;
                }})();
            """)
            if res:
                clicked = True
                break
        if not clicked:
            raise CDPError("Could not find submit button for comment.")
        print("[cdp_publish] Comment replied.")
        time.sleep(ACTION_INTERVAL)

    def _click_long_article_tab(self):
        tab_text = SELECTORS["long_article_tab_text"]
        selector = SELECTORS["image_text_tab"]
        clicked = self._evaluate(f"""
            (function() {{
                var tabs = document.querySelectorAll('{selector}');
                for (var i = 0; i < tabs.length; i++) {{
                    if (tabs[i].textContent.trim() === '{tab_text}') {{
                        tabs[i].click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if not clicked:
            raise CDPError("Could not find long article tab.")
        time.sleep(TAB_CLICK_WAIT)

    def _click_new_creation(self):
        btn_text = SELECTORS["new_creation_btn_text"]
        clicked = self._evaluate(f"""
            (function() {{
                var all = document.querySelectorAll('button, [role=\"button\"], .d-button, [class*=\"btn\"], [class*=\"button\"], .creator-actions *');
                for (var i = 0; i < all.length; i++) {{
                    var t = all[i].textContent && all[i].textContent.trim();
                    if (t === '{btn_text}') {{
                        var el = all[i].closest('button, [role=\"button\"], .d-button');
                        (el || all[i]).click();
                        return true;
                    }}
                }}
                var nodes = document.querySelectorAll('*');
                for (var j = 0; j < nodes.length; j++) {{
                    var t2 = nodes[j].textContent && nodes[j].textContent.trim();
                    if (t2 === '{btn_text}') {{
                        nodes[j].click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if not clicked:
            raise CDPError("Could not find new creation button.")
        time.sleep(ACTION_INTERVAL)

    def _fill_long_title(self, title: str):
        selector = SELECTORS["long_title_input"]
        found = self._evaluate(f"!!document.querySelector('{selector}')")
        if not found:
            raise CDPError("Could not find long title input.")
        escaped = json.dumps(title)
        self._evaluate(f"""
            (function() {{
                var el = document.querySelector('{selector}');
                var setter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value'
                ).set;
                el.focus();
                setter.call(el, {escaped});
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }})();
        """)
        time.sleep(ACTION_INTERVAL)

    def _click_auto_format(self):
        btn_text = SELECTORS["auto_format_btn_text"]
        clicked = self._evaluate(f"""
            (function() {{
                var buttons = document.querySelectorAll('button, [role=\"button\"], .d-button, [class*=\"btn\"], [class*=\"button\"]');
                for (var i = 0; i < buttons.length; i++) {{
                    var t = buttons[i].textContent && buttons[i].textContent.trim();
                    if (t === '{btn_text}') {{
                        buttons[i].click();
                        return true;
                    }}
                }}
                var spans = document.querySelectorAll('.d-button-content .d-text, .d-button-content span');
                for (var j = 0; j < spans.length; j++) {{
                    if (spans[j].textContent.trim() === '{btn_text}') {{
                        var el = spans[j].closest('button, [role=\"button\"], .d-button, [class*=\"btn\"], [class*=\"button\"]');
                        (el || spans[j]).click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if not clicked:
            raise CDPError("Could not find auto format button.")
        time.sleep(AUTO_FORMAT_WAIT)

    def _click_next_step(self):
        btn_text = SELECTORS["next_step_btn_text"]
        clicked = self._evaluate(f"""
            (function() {{
                var buttons = document.querySelectorAll('button, [role=\"button\"], .d-button, [class*=\"btn\"], [class*=\"button\"]');
                for (var i = 0; i < buttons.length; i++) {{
                    var t = buttons[i].textContent && buttons[i].textContent.trim();
                    if (t === '{btn_text}') {{
                        buttons[i].click();
                        return true;
                    }}
                }}
                var nodes = document.querySelectorAll('*');
                for (var j = 0; j < nodes.length; j++) {{
                    var t2 = nodes[j].textContent && nodes[j].textContent.trim();
                    if (t2 === '{btn_text}') {{
                        nodes[j].click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if not clicked:
            raise CDPError("Could not find next step button.")
        time.sleep(ACTION_INTERVAL)

    def _wait_and_click_next_step(self, timeout_s: int = 6):
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                self._click_next_step()
                return
            except CDPError:
                time.sleep(0.5)
        raise CDPError("Could not find next step button.")

    def get_template_names(self) -> list[str]:
        names = self._evaluate(f"""
            (function() {{
                var cards = document.querySelectorAll('{SELECTORS["template_card"]}');
                var out = [];
                for (var i = 0; i < cards.length; i++) {{
                    var t = cards[i].querySelector('.template-title, .title, .d-text');
                    out.push((t && t.textContent && t.textContent.trim()) || '');
                }}
                return out;
            }})();
        """)
        if not isinstance(names, list):
            return []
        return [str(n or "").strip() for n in names]

    def select_template(self, name: str | None = None):
        if name:
            clicked = self._evaluate(f"""
                (function() {{
                    var cards = document.querySelectorAll('{SELECTORS["template_card"]}');
                    for (var i = 0; i < cards.length; i++) {{
                        var t = cards[i].querySelector('.template-title, .title, .d-text');
                        var tn = (t && t.textContent && t.textContent.trim()) || '';
                        if (tn === '{name}') {{
                            cards[i].click();
                            return true;
                        }}
                    }}
                    return false;
                }})();
            """)
            if not clicked:
                raise CDPError("Could not select template by name.")
        else:
            clicked = self._evaluate(f"""
                (function() {{
                    var card = document.querySelector('{SELECTORS["template_card"]}');
                    if (!card) return false;
                    card.click();
                    return true;
                }})();
            """)
            if not clicked:
                raise CDPError("Could not select any template.")
        time.sleep(ACTION_INTERVAL)

    def publish_long_article(self, title: str, content: str, template_name: str | None = None):
        self._navigate(XHS_CREATOR_URL)
        self._click_long_article_tab()
        self._click_new_creation()
        self._fill_long_title(title)
        self._fill_content(content)
        self._click_auto_format()
        try:
            self.select_template(template_name)
        except Exception:
            pass
        self._wait_and_click_next_step(timeout_s=6)


def main():
    import argparse
    from chrome_launcher import ensure_chrome, restart_chrome
    parser = argparse.ArgumentParser(description="Xiaohongshu CDP Publisher")
    parser.add_argument("--headless", action="store_true", help="Use headless Chrome (no GUI window)")
    parser.add_argument("--account", help="Account name to use (default: default account)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-login", help="Check login status (exit 0=logged in, 1=not)")
    p_pub = sub.add_parser("publish", help="Fill form and click publish")
    p_pub.add_argument("--title", required=True)
    p_pub.add_argument("--content", default=None)
    p_pub.add_argument("--content-file", default=None, help="Read content from file")
    p_pub.add_argument("--images", nargs="+", required=True)
    p_reply = sub.add_parser("reply-comment", help="Reply a comment on a note URL")
    p_reply.add_argument("--note-url", required=True)
    p_reply.add_argument("--text", default=None)
    p_reply.add_argument("--text-file", default=None)

    args = parser.parse_args()
    headless = args.headless
    account = args.account
    if not ensure_chrome(headless=headless, account=account):
        print("Failed to start Chrome. Exiting.")
        sys.exit(1)
    publisher = XiaohongshuPublisher()
    try:
        if args.command == "check-login":
            publisher.connect()
            logged_in = publisher.check_login()
            sys.exit(0 if logged_in else 1)
        elif args.command == "publish":
            content = args.content
            if args.content_file:
                with open(args.content_file, encoding="utf-8") as f:
                    content = f.read().strip()
            if not content:
                print("Error: --content or --content-file required.", file=sys.stderr)
                sys.exit(1)
            publisher.connect()
            publisher.publish(title=args.title, content=content, image_paths=args.images)
            publisher._click_publish()
            print("PUBLISH_STATUS: PUBLISHED")
        elif args.command == "reply-comment":
            reply_text = getattr(args, 'text', None)
            if getattr(args, 'text_file', None):
                with open(args.text_file, encoding="utf-8") as f:
                    reply_text = f.read().strip()
            if not reply_text:
                print("Error: --text or --text-file required.", file=sys.stderr)
                sys.exit(1)
            publisher.connect()
            publisher.reply_comment(args.note_url, reply_text)
            print("REPLY_STATUS: SENT")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
