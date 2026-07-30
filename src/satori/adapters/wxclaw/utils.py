import re
from base64 import b64decode, b64encode
from os import urandom
from pathlib import Path
from time import time
from urllib.parse import unquote_to_bytes, urlparse
from urllib.request import url2pathname

DEFAULT_BOT_AGENT = "OpenClaw"
_DATA_URL_PATTERN = re.compile(r"^data:(?P<mime>[^;,]*)(?P<base64>;base64)?,(?P<data>.*)$", re.DOTALL)


def build_base_info(channel_version: str, bot_agent: str = "") -> dict[str, str]:
    return {
        "channel_version": channel_version,
        "bot_agent": bot_agent.strip() or DEFAULT_BOT_AGENT,
    }


def _random_wechat_uin() -> str:
    value = int.from_bytes(urandom(4), "big")
    return b64encode(str(value).encode()).decode()


def parse_client_version(channel_version: str) -> int:
    parts = [*channel_version.split("."), "0", "0", "0"][:3]
    major, minor, patch = (int(value) for value in parts)
    return ((major & 0xFF) << 16) | ((minor & 0xFF) << 8) | (patch & 0xFF)


def build_headers(*, token: str, app_id: str, channel_version: str) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "X-WECHAT-UIN": _random_wechat_uin(),
        "iLink-App-Id": app_id,
        "iLink-App-ClientVersion": str(parse_client_version(channel_version)),
    }
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    return headers


def build_get_headers(*, app_id: str, channel_version: str) -> dict[str, str]:
    return {
        "iLink-App-Id": app_id,
        "iLink-App-ClientVersion": str(parse_client_version(channel_version)),
    }


def generate_client_id() -> str:
    return f"openclaw-weixin:{int(time() * 1000)}-{urandom(4).hex()}"


def parse_file_uri(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"Not a file URI: {uri}")
    path = url2pathname(parsed.path)
    if parsed.netloc and parsed.netloc != "localhost":
        path = f"//{parsed.netloc}{path}"
    return Path(path)


def decode_data_uri(uri: str) -> tuple[str | None, bytes]:
    matched = _DATA_URL_PATTERN.match(uri)
    if not matched:
        raise ValueError("Invalid data URI")
    content_type = matched["mime"] or None
    data = matched["data"]
    if matched["base64"]:
        return content_type, b64decode(data)
    return content_type, unquote_to_bytes(data)
