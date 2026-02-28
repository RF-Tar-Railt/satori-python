from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib.parse import urlparse

from satori.element import Custom, E, Element
from satori.model import Login, MessageObject
from satori.parser import Element as RawElement
from satori.parser import parse

from .utils import USER_AVATAR_URL, OneBotNetwork


class MessageSegment(TypedDict):
    type: str
    data: dict[str, Any]


def uri_to_path(uri):
    parsed = urlparse(uri)
    path_str = parsed.path

    # 在 Windows 上处理驱动器字母
    if path_str.startswith("/") and len(path_str) > 2 and path_str[2] == ":":
        # 删除开头的 '/'，Windows 路径如 /C:/Users 需要转换为 C:/Users
        path_str = path_str[1:]

    return Path(path_str).resolve()


# def escape(text: str, inline: bool = False) -> str:
#     result = text.replace("&", "&amp;").replace("[", "&#91;").replace("]", "&#93;")
#     if inline:
#         result = result.replace(",", "&#44;")
#         result = re.sub(
#             r"(\ud83c[\udf00-\udfff])|(\ud83d[\udc00-\ude4f\ude80-\udeff])|[\u2600-\u2B55]", " ", result
#         )
#     return result
#
#
# def unescape(text: str) -> str:
#     return text.replace("&#91;", "[").replace("&#93;", "]").replace("&#44;", ",").replace("&amp;", "&")


b64_cap = re.compile(r"^data:([\w/.+-]+);base64,")


@dataclass
class State:
    type: Literal["message", "reply", "forward"]
    children: list[MessageSegment] = field(default_factory=list)
    author: dict[str, Any] = field(default_factory=dict)


class OneBot11MessageEncoder:
    def __init__(self, login: Login, net: OneBotNetwork, channel_id: str):
        self.net = net
        self.login = login
        self.channel_id = channel_id
        self.children: list[MessageSegment] = []
        self.stack = [State("message")]
        self.results: list[MessageObject] = []

    async def send_forward(self):
        if not self.stack[0].children:
            return
        if self.channel_id.startswith("private:"):
            resp = await self.net.call_api(
                "send_private_forward_msg",
                {
                    "user_id": int(self.channel_id[8:]),
                    "messages": self.stack[0].children,
                },
            )
        else:
            resp = await self.net.call_api(
                "send_group_forward_msg",
                {
                    "group_id": int(self.channel_id),
                    "messages": self.stack[0].children,
                },
            )
        if resp:
            self.results.append(MessageObject(resp["message_id"], ""))

    async def flush(self):
        if not self.children:
            return

        while True:
            first = self.children[0]
            if first["type"] != "text":
                break
            first["data"]["text"] = first["data"]["text"].lstrip()
            if first["data"]["text"]:
                break
            self.children.pop(0)

        while True:
            last = self.children[-1]
            if last["type"] != "text":
                break
            last["data"]["text"] = last["data"]["text"].rstrip()
            if last["data"]["text"]:
                break
            self.children.pop()

        slot = self.stack[0]
        type_, author = slot.type, slot.author
        if not self.children and "message_id" not in author:
            return
        if type_ == "forward":
            if "message_id" in author:
                self.stack[1].children.append(
                    {
                        "type": "node",
                        "data": {
                            "id": author["message_id"],
                        },
                    }
                )
            else:
                self.stack[1].children.append(
                    {
                        "type": "node",
                        "data": {
                            "name": author.get(
                                "name",
                                (self.login.user.name or self.login.user.id) if self.login.user else "",
                            ),
                            "uin": author.get("id", self.login.user.id if self.login.user else 0),
                            "content": self.children,
                            "time": int(datetime.now().timestamp()),
                        },
                    }
                )

            self.children = []
            return

        if self.channel_id.startswith("private:"):
            resp = await self.net.call_api(
                "send_private_msg",
                {
                    "user_id": int(self.channel_id[8:]),
                    "message": self.children,
                },
            )
        else:
            resp = await self.net.call_api(
                "send_group_msg",
                {
                    "group_id": int(self.channel_id),
                    "message": self.children,
                },
            )
        if resp:
            self.results.append(MessageObject(resp["message_id"], ""))
        self.children = []

    async def _send_file(self, attrs: dict[str, Any]):
        src = attrs.get("src") or attrs["url"]
        if src.startswith("file:"):
            file = uri_to_path(src)
            name = file.name
        elif mat := b64_cap.match(src):
            file = f"base64://{src[len(mat[0]):]}"
            name = attrs.get("title")
        else:
            file = src
            name = attrs.get("title") or src.split("/")[-1][:32]
        if self.channel_id.startswith("private:"):
            await self.net.call_api(
                "upload_private_file",
                {
                    "user_id": int(self.channel_id[8:]),
                    "file": str(file),
                    "name": name,
                },
            )
        else:
            await self.net.call_api(
                "upload_group_file",
                {
                    "group_id": int(self.channel_id),
                    "file": str(file),
                    "name": name,
                },
            )
        self.results.append(MessageObject("", ""))

    async def send(self, content: str):
        await self.render(parse(content))
        await self.flush()
        return self.results

    async def render(self, elements: list[RawElement]):
        for element in elements:
            await self.visit(element)

    async def visit(self, element: RawElement):
        type_, attrs, _children = element.type, element.attrs, element.children
        match type_:
            case "text":
                self.children.append({"type": "text", "data": {"text": attrs["text"]}})
            case "br":
                self.children.append({"type": "text", "data": {"text": "\n"}})
            case "p":
                prev = self.children[-1] if self.children else None
                if prev and prev["type"] == "text":
                    if not prev["data"]["text"].endswith("\n"):
                        prev["data"]["text"] += "\n"
                else:
                    self.children.append({"type": "text", "data": {"text": "\n"}})
                await self.render(_children)
                self.children.append({"type": "text", "data": {"text": "\n"}})
            case "at":
                if "type" in attrs and attrs["type"] == "all":
                    self.children.append({"type": "at", "data": {"qq": "all"}})
                else:
                    self.children.append({"type": "at", "data": {"qq": str(attrs["id"]), "name": attrs.get("name")}})
            case "sharp":
                if "id" in attrs:
                    self.children.append({"type": "text", "data": {"text": attrs["id"]}})
            case "onebot:face" | "emoji":
                if ":" in attrs["id"]:
                    _, emj_id_str = attrs["id"].split(":", 1)
                    emj_id = int(emj_id_str)
                else:
                    emj_id = int(attrs["id"])
                self.children.append({"type": "face", "data": {"id": emj_id}})
            case "a":
                await self.render(_children)
                if "href" in attrs:
                    self.children.append({"type": "text", "data": {"text": f" ({attrs['href']})"}})
            case "video" | "audio" | "img" | "image":
                if type_ in ("video", "audio"):
                    await self.flush()
                if type_ == "audio":
                    type_ = "record"
                elif type_ == "img":
                    type_ = "image"
                _data = {
                    "cache": 1 if "cache" in attrs and attrs["cache"] else 0,
                    "file": attrs.get("src") or attrs.get("url"),
                }
                if mat := b64_cap.match(_data["file"]):
                    _data["file"] = f"base64://{_data['file'][len(mat[0]):]}"
                self.children.append({"type": type_, "data": _data})
            case "file":
                await self.flush()
                await self._send_file(attrs)
            case "onebot:music":
                await self.flush()
                self.children.append({"type": "music", "data": attrs})
            case "onebot:poke":
                await self.flush()
                self.children.append({"type": "poke", "data": attrs})
            case "onebot:gift":
                await self.flush()
                self.children.append({"type": "gift", "data": attrs})
            case "onebot:share":
                await self.flush()
                self.children.append({"type": "share", "data": attrs})
            case "onebot:json":
                await self.flush()
                self.children.append({"type": "json", "data": attrs})
            case "onebot:xml":
                await self.flush()
                self.children.append({"type": "xml", "data": attrs})
            case "author":
                self.stack[0].author.update(attrs)
            case "quote":
                await self.flush()
                self.children.append({"type": "reply", "data": attrs})
            case "message":
                await self.flush()
                if "forward" in attrs:
                    self.stack.insert(0, State("forward"))
                    await self.render(_children)
                    await self.flush()
                    self.stack.pop(0)
                    await self.send_forward()
                elif "id" in attrs:
                    self.stack[0].author["message_id"] = str(attrs["id"])
                else:
                    payload = {}
                    if "name" in attrs:
                        payload["name"] = attrs["name"]
                    if "nickname" in attrs:
                        payload["name"] = attrs["nickname"]
                    if "username" in attrs:
                        payload["name"] = attrs["username"]
                    if "id" in attrs:
                        payload["id"] = int(attrs["id"])
                    if "user_id" in attrs:
                        payload["id"] = int(attrs["user_id"])
                    if "time" in attrs:
                        payload["time"] = int(attrs["time"])
                    self.stack[0].author.update(payload)
                    await self.render(_children)
                    await self.flush()
            case _:
                await self.render(_children)


async def _decode(content: list[MessageSegment], net: OneBotNetwork) -> list[Element]:
    result = []
    for seg in content:
        seg_type = seg["type"]
        seg_data = seg["data"]
        match seg_type:
            case "text":
                result.append(E.text(seg_data["text"]))
            case "at":
                qq = seg_data["qq"]
                if qq == "all":
                    result.append(E.at_all())
                else:
                    result.append(E.at(str(qq), name=seg_data.get("name")))
            case "face":
                result.append(E.emoji(str(seg_data["id"])))
            case "image":
                result.append(E.image(seg_data.get("url") or seg_data.get("file")))
            case "record":
                result.append(E.audio(seg_data.get("url") or seg_data.get("file")))
            case "video":
                result.append(E.video(seg_data.get("url") or seg_data.get("file")))
            case "file":
                result.append(E.file(seg_data.get("url") or seg_data.get("file")))
            case "reply":
                if msg := (await net.call_api("get_msg", {"message_id": seg_data["id"]})):
                    author = E.author(
                        str(msg["sender"]["user_id"]),
                        msg["sender"]["nickname"],
                        USER_AVATAR_URL.format(uin=msg["sender"]["user_id"]),
                    )
                    result.append(E.quote(seg_data["id"], content=[author, *(await _decode(msg["message"], net))]))
            case _:
                result.append(Custom(f"onebot:{seg_type}", seg_data))
    return result


async def decode(content: list[MessageSegment], net: OneBotNetwork) -> str:
    return "".join(str(x) for x in await _decode(content, net))
