from __future__ import annotations

import base64
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from satori.element import Button, Custom, E, Element, select, transform
from satori.model import Login, MessageObject
from satori.parser import Element as RawElement
from satori.parser import parse

from ...exception import ActionFailed
from .exception import AuditException
from .utils import QQBotNetwork

_BASE64_RE = re.compile(r"^data:([\w/.+-]+);base64,")


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unescape(s: str) -> str:
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def escape_markdown(s: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+\-.!>~])", r"\\\1", s)


def handle_text(msg: str):
    text_begin = 0
    msg = msg.replace("@everyone", "")
    msg = re.sub(r"\<qqbot-at-everyone\s/\>", "", msg)
    for embed in re.finditer(
        r"\<(?P<type>(?:@|#|emoji:))!?(?P<id>\w+?)\>|\<(?P<type1>qqbot-at-user) id=\"(?P<id1>\w+)\"\s/\>",
        msg,
    ):
        if content := msg[text_begin : embed.pos + embed.start()]:
            yield {"type": "text", "text": unescape(content)}
        text_begin = embed.pos + embed.end()
        if embed["type"] == "@":
            yield {"type": "mention_user", "user_id": embed.group("id")}
        elif embed["type"] == "#":
            yield {"type": "mention_channel", "channel_id": embed.group("id")}
        elif embed["type"] == "emoji":
            yield {"type": "emoji", "id": embed.group("id")}
        elif embed["type1"] == "qqbot-at-user":
            yield {"type": "mention_user", "user_id": embed.group("id1")}
    if content := msg[text_begin:]:
        yield {"type": "text", "text": unescape(content)}


def form_data(message: dict):
    if not (file_image := message.pop("file_image", None)):
        return "post", message
    files = {"file_image": {"value": file_image, "content_type": None, "filename": "file_image"}}
    data_ = {}
    for key, value in message.items():
        if isinstance(value, (list, dict)):
            files[key] = {
                "value": json.dumps({key: value}).encode("utf-8"),
                "content_type": "application/json",
                "filename": f"{key}.json",
            }
        else:
            data_[key] = value
    return "multipart", {"files": files, "data": data_}


def remove_empty(d: dict):
    return {k: (remove_empty(v) if isinstance(v, dict) else v) for k, v in d.items() if v is not None}


class QQBotMessageEncoder:
    def __init__(self, login: Login, net: QQBotNetwork, channel_id: str, referrer: dict | None = None):
        self.login = login
        self.net = net
        self.channel_id = channel_id
        self.referrer = referrer
        self.results: list[MessageObject] = []
        self._raw_content = ""

    async def send(self, content: str):
        self._raw_content = content
        msg = transform(parse(content))
        btns = select(msg, Button)
        btns = [btn for btn in btns if btn.type != "link" and not btn.id]
        for btn in btns:
            btn.id = random.randbytes(8).hex()
        await self.render(parse("".join(map(str, msg))))
        await self.flush()
        return self.results

    async def flush(self): ...
    async def visit(self, element: RawElement): ...

    async def render(self, elements: list[RawElement]):
        for element in elements:
            await self.visit(element)


class QQGuildMessageEncoder(QQBotMessageEncoder):
    def __init__(self, login: Login, net: QQBotNetwork, channel_id: str, referrer: dict | None = None):
        super().__init__(login, net, channel_id, referrer)
        self.reference = ""
        self.content = ""
        self.file_url = ""
        self.file_data = {}  # value, content_type, filename

    async def flush(self):
        if not self.content.strip() and not self.file_url and not self.file_data:
            return
        is_direct = "_" in self.channel_id or (self.referrer and self.referrer.get("direct", False))
        endpoint = f"channels/{self.channel_id}/messages"
        if is_direct:
            endpoint = f"dms/{self.channel_id.split('_')[0]}/messages"
        msg_id = self.referrer.get("msg_id") if self.referrer else None
        msg_seq = self.referrer.get("msg_seq") if self.referrer else None
        if isinstance(msg_seq, int) and msg_seq >= 5:
            return
        try:
            if self.file_data:
                files = {"file_image": self.file_data}
                message = {
                    "content": self.content,
                    "message_reference": {"message_id": self.reference} if self.reference else None,
                    "msg_id": msg_id,
                }
                message = remove_empty(message)
                data_ = {}
                for key, value in message.items():
                    if isinstance(value, (list, dict)):
                        files[key] = {
                            "value": json.dumps({key: value}).encode("utf-8"),
                            "content_type": "application/json",
                            "filename": f"{key}.json",
                        }
                    else:
                        data_[key] = value
                resp = await self.net.call_api("multipart", endpoint, {"files": files, "data": data_})
            else:
                message = {
                    "content": self.content,
                    "message_reference": {"message_id": self.reference} if self.reference else None,
                    "image": self.file_url if self.file_url else None,
                    "msg_id": msg_id,
                }
                message = remove_empty(message)
                resp = await self.net.call_api("post", endpoint, message)
            referrer = self.referrer.copy() if self.referrer else {}
            referrer |= {
                "msg_id": msg_id,
                "msg_seq": (msg_seq + 1) if isinstance(msg_seq, int) else 0,
            }
            self.results.append(MessageObject(resp["id"], self._raw_content, referrer=referrer))
        except AuditException as e:
            audit_res = await e.get_audit_result()
            if not audit_res or not audit_res.message_id:
                logger.error(f"Failed to send message to {self.channel_id}: {self._raw_content}")
            else:
                referrer = self.referrer.copy() if self.referrer else {}
                referrer |= {
                    "msg_id": msg_id,
                    "msg_seq": (msg_seq + 1) if isinstance(msg_seq, int) else 0,
                }
                self.results.append(MessageObject(audit_res.message_id, self._raw_content, referrer=referrer))
        except Exception as e:
            logger.error(f"Failed to send message to {self.channel_id}: {self._raw_content}\nError: {e}")
        self.content = ""
        self.file_url = ""
        self.file_data = {}
        self.reference = ""

    async def visit(self, element: RawElement):
        type_, attrs, children = element.type, element.attrs, element.children
        match type_:
            case "text":
                self.content += attrs["text"]
            case "at":
                self.content += (
                    "<qqbot-at-everyone />"
                    if "type" in attrs and attrs["type"] == "all"
                    else f"<qqbot-at-user id=\"{attrs['id']}\" />"
                )
            case "br":
                self.content += "\n"
            case "p":
                if not self.content.endswith("\n"):
                    self.content += "\n"
                await self.render(children)
                if not self.content.endswith("\n"):
                    self.content += "\n"
            case "sharp":
                self.content += f"<#!{attrs['id']}>"
            case "quote":
                self.reference = attrs["id"]
                await self.flush()
            case "message":
                await self.flush()
                await self.render(children)
                await self.flush()
            case "img" | "image":
                if attrs.get("src") or attrs.get("url"):
                    await self.flush()
                    self.resolve_file(attrs)
                    await self.flush()
            case "qq:emoji" | "emoji":
                self.content += f"<emoji:{attrs['id']}>"
            case _:
                await self.render(children)

    def resolve_file(self, attrs: dict, download: bool = False):
        url = attrs.get("url") or attrs["src"]
        is_uri = url.startswith("file://")
        b64_match = _BASE64_RE.match(url)
        if not download and not is_uri and not b64_match:
            self.file_url = url
            self.file_data = {}
        else:
            self.file_url = ""
            if b64_match:
                b64_data = url[len(b64_match.group(0)) :]
                data = base64.b64decode(b64_data)
                content_type = b64_match.group(1)
                filename = f"file.{content_type.split('/')[-1]}"
            else:
                path = Path(url[7:])
                data = path.read_bytes()
                filename = path.name
                content_type = None
            self.file_data = {"value": data, "content_type": content_type, "filename": filename}


class QQGroupMessageEncoder(QQBotMessageEncoder):
    def __init__(self, login: Login, net: QQBotNetwork, channel_id: str, referrer: dict | None = None):
        super().__init__(login, net, channel_id, referrer)
        self.use_markdown = False
        self.content = ""
        self.attachment: dict | None = None
        self.rows: list[list[dict]] = []
        # self.file_url = ""
        # self.file_data = {}  # value, content_type, filename

    async def flush(self):
        if not self.content and not self.attachment and not self.rows:
            return
        self.strip_buttons()
        msg_id = self.referrer.get("msg_id") if self.referrer else None
        msg_seq = self.referrer.get("msg_seq") if self.referrer else None
        data = {
            "content": self.content,
            "msg_type": 0,
            "msg_id": msg_id,
            "msg_seq": (msg_seq + 1) if isinstance(msg_seq, int) else 0,
        }
        if self.attachment:
            if not self.content:
                self.content = " "
            data["media"] = self.attachment
            data["msg_type"] = 7
        if self.use_markdown:
            data["msg_type"] = 2
            del data["content"]
            data["markdown"] = {
                "content": escape_markdown(self.content) or " ",
            }
            if self.rows:
                data["keyboard"] = {"content": {"rows": self.export_buttons()}}
        try:
            if self.channel_id.startswith("private:") or (self.referrer and self.referrer.get("direct", False)):
                endpoint = f"v2/users/{self.channel_id.split(':',1)[-1]}/messages"
            else:
                endpoint = f"v2/groups/{self.channel_id}/messages"
            try:
                resp = await self.net.call_api("post", endpoint, remove_empty(data))
            except ActionFailed:
                data["msg_seq"] = (
                    data["msg_seq"] + (hash(self.channel_id) % 0x7FFFFFF) + int(datetime.now(timezone.utc).timestamp())
                )
                resp = await self.net.call_api("post", endpoint, remove_empty(data))
            referrer = self.referrer.copy() if self.referrer else {}
            referrer |= {
                "msg_id": msg_id,
                "msg_seq": data["msg_seq"],
            }
            self.results.append(MessageObject(resp["id"], self._raw_content, referrer=referrer))
        except Exception as e:
            logger.error(f"Failed to send message to {self.channel_id}: {self._raw_content}\nError: {e}")
        self.content = ""
        self.attachment = None
        self.use_markdown = False
        self.rows = []

    async def send_file(self, type_: str, attrs: dict) -> dict | None:
        url = attrs.get("url") or attrs["src"]
        is_uri = url.startswith("file://")
        b64_match = _BASE64_RE.match(url)
        file_type = 0
        match type_:
            case "img" | "image":
                file_type = 1
            case "audio":
                file_type = 2
            case "video":
                file_type = 3
            case _:
                file_type = 4
        req: dict = {
            "file_type": file_type,
            "srv_send_msg": False,
        }
        if b64_match:
            req["file_data"] = url[len(b64_match.group(0)) :]
        elif is_uri:
            path = Path(url[7:])
            req["file_data"] = base64.b64encode(path.read_bytes()).decode("utf-8")
        else:
            req["url"] = url
        if self.channel_id.startswith("private:") or (self.referrer and self.referrer.get("direct", False)):
            endpoint = f"v2/users/{self.channel_id.split(':',1)[-1]}/files"
        else:
            endpoint = f"v2/groups/{self.channel_id}/files"
        try:
            resp = await self.net.call_api("post", endpoint, req)
            return resp
        except Exception as e:
            logger.error(f"Failed to upload file to {self.channel_id}: {url}\nError: {e}")
            return None

    async def visit(self, element: RawElement):
        type_, attrs, children = element.type, element.attrs, element.children
        match type_:
            case "text":
                self.content += attrs["text"]
            case "img" | "image":
                if attrs.get("src") or attrs.get("url"):
                    await self.flush()
                    if data := (await self.send_file(type_, attrs)):
                        self.attachment = data
            case "video" | "audio" | "file":
                if attrs.get("src") or attrs.get("url"):
                    await self.flush()
                    if data := (await self.send_file(type_, attrs)):
                        self.attachment = data
                    await self.flush()
            case "br":
                self.content += "\n"
            case "p":
                if not self.content.endswith("\n"):
                    self.content += "\n"
                await self.render(children)
                if not self.content.endswith("\n"):
                    self.content += "\n"
            case "qq:button-group":
                self.use_markdown = True
                self.rows.append([])
                await self.render(children)
                self.rows.append([])
            case "button":
                self.use_markdown = True
                last = self.last_row()
                last.append(self.decode_button(attrs, "".join(map(str, children))))
            case "markdown":
                self.use_markdown = True
                await self.render(children)
            case "message":
                await self.flush()
                await self.render(children)
                await self.flush()
            case _:
                await self.render(children)

    def last_row(self) -> list[dict]:
        if not self.rows:
            self.rows.append([])
        last = self.rows[-1]
        if len(last) >= 5:
            self.rows.append([])
            last = self.rows[-1]
        return last

    def strip_buttons(self):
        if self.rows and not self.rows[-1]:
            self.rows.pop()

    def export_buttons(self):
        return [{"buttons": row} for row in self.rows]

    def decode_button(self, attrs: dict, label: str) -> dict:
        return {
            "id": attrs["id"],
            "render_data": {
                "label": label,
                "visited_label": label,
                "style": 1 if attrs.get("class") == "primary" else 0,
            },
            "action": {
                "type": {"input": 2, "link": 0}.get(attrs.get("type", "action"), 1),
                "permission": {"type": 2},
                "data": {
                    "input": attrs.get("text"),
                    "link": attrs.get("href"),
                }.get(attrs.get("type", "action"), attrs["id"]),
            },
        }


def _decode_attachment(attachment: dict) -> Element:
    if "content_type" not in attachment:
        return E.image(src=attachment["url"])
    mime = attachment["content_type"]
    if mime.startswith("image/"):
        return E.image(
            url=attachment["url"],
            mime=mime,
            name=attachment.get("filename"),
            height=attachment.get("height"),
            width=attachment.get("width"),
        )
    elif mime.startswith("audio/"):
        return E.audio(
            url=attachment["url"], mime=mime, name=attachment.get("filename"), duration=attachment.get("duration")
        )
    elif mime.startswith("video/"):
        return E.video(
            url=attachment["url"],
            mime=mime,
            name=attachment.get("filename"),
            height=attachment.get("height"),
            width=attachment.get("width"),
            duration=attachment.get("duration"),
        )
    else:
        return E.file(
            url=attachment["url"], mime=mime, name=attachment.get("filename"), extra={"size": attachment.get("size")}
        )


def decode_segments(event: dict) -> list[Element]:
    result: list[Element] = []
    if message_reference := event.get("message_reference"):
        result.append(E.quote(message_reference["message_id"]))
    if event.get("mention_everyone", False):
        result.append(E.at_all())
    if "content" in event:
        for i in handle_text(event["content"]):
            seg_type = i["type"]
            if seg_type == "text":
                result.append(E.text(i["text"]))
            elif seg_type == "mention_user":
                result.append(E.at(i["user_id"]))
            elif seg_type == "mention_channel":
                result.append(E.sharp(i["channel_id"]))
            elif seg_type == "emoji":
                result.append(E.emoji(i["id"]))
    if attachments := event.get("attachments"):
        for i in attachments:
            result.append(_decode_attachment(i))
    if embeds := event.get("embeds"):
        for i in embeds:
            result.append(Custom("qq:embed", i))
    if ark := event.get("ark"):
        result.append(Custom("qq:ark", ark))
    return result
