from __future__ import annotations

import re
from base64 import b64decode
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal, TypedDict
from urllib.parse import urlparse

from graia.amnesia.builtins.aiohttp import AiohttpClientService
from launart import Launart

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

    return Path(path_str)


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
        manager = Launart.current()
        aio = manager.get_component(AiohttpClientService)
        src = attrs.get("src") or attrs["url"]
        name = attrs.get("title") or src.split("/")[-1][:32]
        temp_dir = TemporaryDirectory()
        if src.startswith("file:"):
            file = uri_to_path(src)
        else:
            file = Path(temp_dir.name).joinpath(f"{id(src)}.tmp")
            if src.startswith("data://"):
                _, b64 = src[5:].split(";", 1)
                with file.open("wb") as f:
                    f.write(b64decode(b64[7:]))
            else:
                async with aio.session.get(src) as resp:
                    with file.open("wb") as f:
                        f.write(await resp.read())
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
        if type_ == "text":
            self.children.append({"type": "text", "data": {"text": attrs["text"]}})
        elif type_ == "br":
            self.children.append({"type": "text", "data": {"text": "\n"}})
        elif type_ == "p":
            prev = self.children[-1] if self.children else None
            if prev and prev["type"] == "text":
                if not prev["data"]["text"].endswith("\n"):
                    prev["data"]["text"] += "\n"
            else:
                self.children.append({"type": "text", "data": {"text": "\n"}})
            await self.render(_children)
            self.children.append({"type": "text", "data": {"text": "\n"}})
        elif type_ == "at":
            if "type" in attrs and attrs["type"] == "all":
                self.children.append({"type": "at", "data": {"qq": "all"}})
            else:
                self.children.append(
                    {"type": "at", "data": {"qq": int(attrs["id"]), "name": attrs.get("name")}}
                )
        elif type_ == "sharp":
            if "id" in attrs:
                self.children.append({"type": "text", "data": {"text": attrs["id"]}})
        elif type_ == "onebot:face":
            self.children.append({"type": "face", "data": {"id": int(attrs["id"])}})
        elif type_ == "a":
            await self.render(_children)
            if "href" in attrs:
                self.children.append({"type": "text", "data": {"text": f" ({attrs['href']})"}})
        elif type_ in ("video", "audio", "img", "image"):
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
        elif type_ == "file":
            await self.flush()
            await self._send_file(attrs)
        elif type_ == "onebot:music":
            await self.flush()
            self.children.append({"type": "music", "data": attrs})
        elif type_ == "onebot:poke":
            await self.flush()
            self.children.append({"type": "poke", "data": attrs})
        elif type_ == "onebot:gift":
            await self.flush()
            self.children.append({"type": "gift", "data": attrs})
        elif type_ == "onebot:share":
            await self.flush()
            self.children.append({"type": "share", "data": attrs})
        elif type_ == "onebot:json":
            await self.flush()
            self.children.append({"type": "json", "data": attrs})
        elif type_ == "onebot:xml":
            await self.flush()
            self.children.append({"type": "xml", "data": attrs})
        elif type_ == "author":
            self.stack[0].author = attrs.copy()
        elif type_ == "quote":
            await self.flush()
            self.children.append({"type": "reply", "data": attrs})
        elif type_ == "message":
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
                self.stack[0].author = {
                    k: v for k, v in attrs.items() if k in ("user_id", "username", "nickname", "time")
                }
                await self.render(_children)
                await self.flush()
        else:
            await self.render(_children)


async def _decode(content: list[MessageSegment], net: OneBotNetwork) -> list[Element]:
    result = []
    for seg in content:
        seg_type = seg["type"]
        seg_data = seg["data"]
        if seg_type == "text":
            result.append(E.text(seg_data["text"]))
        elif seg_type == "at":
            qq = seg_data["qq"]
            if qq == "all":
                result.append(E.at_all())
            else:
                result.append(E.at(str(qq), name=seg_data.get("name")))
        elif seg_type == "image":
            result.append(E.image(seg_data.get("url") or seg_data.get("file")))
        elif seg_type == "record":
            result.append(E.audio(seg_data.get("url") or seg_data.get("file")))
        elif seg_type == "video":
            result.append(E.video(seg_data.get("url") or seg_data.get("file")))
        elif seg_type == "file":
            result.append(E.file(seg_data.get("url") or seg_data.get("file")))
        elif seg_type == "reply":
            if msg := (await net.call_api("get_msg", {"message_id": seg_data["id"]})):
                author = E.author(
                    str(msg["sender"]["user_id"]),
                    msg["sender"]["nickname"],
                    USER_AVATAR_URL.format(uin=msg["sender"]["user_id"]),
                )
                result.append(
                    E.quote(seg_data["id"], content=[author, *(await _decode(msg["message"], net))])
                )
        else:
            result.append(Custom(f"onebot:{seg_type}", seg_data))
    return result


async def decode(content: list[MessageSegment], net: OneBotNetwork) -> str:
    return "".join(str(x) for x in await _decode(content, net))
