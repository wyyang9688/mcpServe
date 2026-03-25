import requests
import json
import time
from typing import Any


class WeChatPublisher:
    def __init__(self, appid: str, appsecret: str) -> None:
        self.appid = appid
        self.appsecret = appsecret
        self.access_token: str | None = None
        self.token_expires_at: float = 0.0

    def get_stable_access_token(self) -> str:
        url = "https://api.weixin.qq.com/cgi-bin/stable_token"
        data = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.appsecret,
        }
        resp = requests.post(url, json=data, timeout=30)
        result: dict[str, Any] = resp.json()
        if "access_token" not in result:
            raise RuntimeError(f"stable_token_error {result}")
        self.access_token = str(result["access_token"])
        self.token_expires_at = time.time() + float(result.get("expires_in", 7200)) - 300
        return self.access_token

    def get_access_token_legacy(self) -> str:
        url = (
            f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.appid}&secret={self.appsecret}"
        )
        resp = requests.get(url, timeout=30)
        result: dict[str, Any] = resp.json()
        if "access_token" not in result:
            raise RuntimeError(f"legacy_token_error {result}")
        self.access_token = str(result["access_token"])
        self.token_expires_at = time.time() + float(result.get("expires_in", 7200)) - 300
        return self.access_token

    def ensure_valid_token(self) -> str:
        if not self.access_token or time.time() >= self.token_expires_at:
            try:
                return self.get_stable_access_token()
            except Exception as e:
                msg = str(e)
                if "40164" in msg or "invalid ip" in msg:
                    return self.get_access_token_legacy()
                raise
        return self.access_token

    def upload_image(self, image_path: str) -> dict[str, str]:
        token = self.ensure_valid_token()
        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"
        with open(image_path, "rb") as f:
            files = {"media": f}
            resp = requests.post(url, files=files, timeout=60)
        result: dict[str, Any] = resp.json()
        if "media_id" not in result:
            raise RuntimeError(f"上传失败: {result}")
        media_id = str(result["media_id"])
        media_url = str(result.get("url", "")) if result.get("url") is not None else ""
        return {"media_id": media_id, "url": media_url}

    def add_draft(self, title: str, content: str, author: str = "", thumb_media_id: str = "", digest: str = "") -> str:
        token = self.ensure_valid_token()
        url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
        payload = {
            "articles": [
                {
                    "title": title,
                    "author": author,
                    "digest": digest or title[:50],
                    "content": content,
                    "content_source_url": "",
                    "thumb_media_id": thumb_media_id,
                    "need_open_comment": 0,
                    "only_fans_can_comment": 0,
                    "show_cover_pic": 1,
                }
            ]
        }
        # 使用 ensure_ascii=False 发送 UTF-8 中文字符，避免服务端保存被转义的内容
        resp = requests.post(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=60,
        )
        result: dict[str, Any] = resp.json()
        if "media_id" not in result:
            raise RuntimeError(f"创建失败: {result}")
        return str(result["media_id"])
