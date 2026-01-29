from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from satori.element import Custom, E, Element
from satori.model import Channel, ChannelType, Login, MessageObject, User
from satori.parser import Element as RawElement
from satori.parser import parse

from .utils import QQBotNetwork

_BASE64_RE = re.compile(r"^data:([\w/.+-]+);base64,")



def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unescape(s: str) -> str:
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


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
        self.segments: list[dict[str, Any]] = []
        self.results: list[MessageObject] = []
    #
    # async def _send_file(self, attrs: dict[str, Any]):
    #     uri = attrs.get("src") or attrs.get("url")
    #     if not uri:
    #         return
    #     name = attrs.get("title") or uri.split("/")[-1]
    #     if match := _BASE64_RE.match(uri):
    #         uri = f"base64://{uri[len(match.group(0)) :]}"
    #     scene, peer_id = get_scene_and_peer(self.channel_id)
    #     if scene == "group":
    #         await self.net.call_api(
    #             "upload_group_file",
    #             {
    #                 "group_id": peer_id,
    #                 "file_uri": uri,
    #                 "file_name": name,
    #             },
    #         )
    #     else:
    #         await self.net.call_api(
    #             "upload_private_file",
    #             {
    #                 "user_id": peer_id,
    #                 "file_uri": uri,
    #                 "file_name": name,
    #             },
    #         )
    #     self.results.append(MessageObject("", ""))

    async def send(self, content: str) -> list[MessageObject]:
        raw_elements = parse(content)
        await self.render(raw_elements)
        await self.flush()
        return self.results

    async def render(self, elements: Sequence[RawElement]):
        for element in elements:
            await self.visit(element)

    async def visit(self, element: RawElement):
        type_ = element.type
        attrs = element.attrs
        children = element.children
        if type_ == "text":
            text = attrs.get("text", "")
            if not self.segments or self.segments[-1]["type"] != "text":
                self.segments.append({"type": "text", "data": {"text": text}})
            else:
                self.segments[-1]["data"]["text"] += text
        elif type_ == "br":
            if not self.segments or self.segments[-1]["type"] != "text":
                self.segments.append({"type": "text", "data": {"text": "\n"}})
            else:
                self.segments[-1]["data"]["text"] += "\n"
        elif type_ == "p":
            prev = self.segments[-1] if self.segments else None
            if prev and prev["type"] == "text":
                if not prev["data"]["text"].endswith("\n"):
                    prev["data"]["text"] += "\n"
            else:
                self.segments.append({"type": "text", "data": {"text": "\n"}})
            await self.render(children)
            if self.segments and self.segments[-1]["type"] == "text":
                if not self.segments[-1]["data"]["text"].endswith("\n"):
                    self.segments[-1]["data"]["text"] += "\n"
            else:
                self.segments.append({"type": "text", "data": {"text": "\n"}})
        elif type_ == "at":
            if attrs.get("type") == "all":
                self.segments.append({"type": "mention_all", "data": {}})
            elif "id" in attrs:
                target = attrs["id"]
                self.segments.append({"type": "mention", "data": {"user_id": int(target)}})
        elif type_ == "sharp":
            self.segments.append({"type": "text", "data": {"text": attrs["id"]}})
        elif type_ == "a":
            await self.render(children)
            if "href" in attrs:
                if not self.segments or self.segments[-1]["type"] != "text":
                    self.segments.append({"type": "text", "data": {"text": f" ({attrs['href']})"}})
                else:
                    self.segments[-1]["data"]["text"] += f" ({attrs['href']})"
        elif type_ in {"img", "image"}:
            uri = attrs.get("src") or attrs.get("url")
            if not uri:
                return
            if match := _BASE64_RE.match(uri):
                uri = f"base64://{uri[len(match.group(0)) :]}"
            self.segments.append({"type": "image", "data": {"uri": uri, "sub_type": attrs.get("sub_type", "normal")}})
        elif type_ == "audio":
            uri = attrs.get("src") or attrs.get("url")
            if not uri:
                return
            if match := _BASE64_RE.match(uri):
                uri = f"base64://{uri[len(match.group(0)) :]}"
            self.segments.append({"type": "record", "data": {"uri": uri}})
        elif type_ == "video":
            uri = attrs.get("src") or attrs.get("url")
            if not uri:
                return
            if match := _BASE64_RE.match(uri):
                uri = f"base64://{uri[len(match.group(0)) :]}"
            payload = {"uri": uri}
            if poster := attrs.get("poster"):
                payload["thumb_uri"] = poster
            self.segments.append({"type": "video", "data": payload})
        elif type_ == "milky:face":
            self.segments.append({"type": "face", "data": {"face_id": attrs["id"]}})
        elif type_ == "file":
            await self.flush()
            await self._send_file(attrs)
        elif type_ == "author":
            self.stack[0].author.update(attrs)
        elif type_ == "quote":
            await self.flush()
            self.segments.append({"type": "reply", "data": {"message_seq": int(attrs["id"])}})
        elif type_ == "message":
            await self.flush()
            if "forward" in attrs:
                self.stack.insert(0, State("forward"))
                await self.render(children)
                await self.flush()
                self.stack.pop(0)
                await self.send_forward()
            elif "id" in attrs:
                self.stack[0].author["seq"] = int(attrs["id"])
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
                await self.render(children)
                await self.flush()
        else:
            await self.render(children)

    async def flush(self):
        if not self.segments:
            return

        while True:
            first = self.segments[0]
            if first["type"] != "text":
                break
            first["data"]["text"] = first["data"]["text"].lstrip()
            if first["data"]["text"]:
                break
            self.segments.pop(0)

        while True:
            last = self.segments[-1]
            if last["type"] != "text":
                break
            last["data"]["text"] = last["data"]["text"].rstrip()
            if last["data"]["text"]:
                break
            self.segments.pop()

        scene, peer_id = get_scene_and_peer(self.channel_id)
        if not self.segments :
            return

        if scene == "group":
            resp = await self.net.call_api("send_group_message", {"group_id": peer_id, "message": self.segments})
        else:
            resp = await self.net.call_api("send_private_message", {"user_id": peer_id, "message": self.segments})
        if resp:
            channel_type = ChannelType.TEXT if scene == "group" else ChannelType.DIRECT
            channel_id = str(peer_id) if scene == "group" else self.channel_id
            channel = Channel(channel_id, channel_type)
            created_at = datetime.fromtimestamp(resp.get("time", datetime.now().timestamp()))
            message = MessageObject(str(resp.get("message_seq", "")), "", channel=channel, created_at=created_at)
            self.results.append(message)
        self.segments = []

    async def sendable(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        new = []
        for seg in segments:
            if (
                seg["type"] in ("image", "record", "video")
                and "resource_id" in seg["data"]
                and "uri" not in seg["data"]
            ):
                data = seg["data"]
                if "temp_url" not in data:
                    data["uri"] = (
                        await self.net.call_api("get_resource_temp_url", {"resource_id": data["resource_id"]})
                    )["url"]
                else:
                    data["uri"] = data["temp_url"]
                new.append({"type": seg["type"], "data": data})
            elif seg["type"] == "forward" and "forward_id" in seg["data"]:
                forward_id = seg["data"]["forward_id"]
                messages = (await self.net.call_api("get_forwarded_messages", {"forward_id": forward_id}))["messages"]
                new.append(
                    {
                        "type": "forward",
                        "data": {
                            "messages": [
                                {
                                    "user_id": int(self.login.id),
                                    "sender_name": msg["sender_name"],
                                    "segments": await self.sendable(msg["segments"]),
                                }
                                for msg in messages
                            ]
                        },
                    }
                )
            elif seg["type"] in ("market_face", "light_app", "xml"):
                continue
        return new


def _decode_attachment(attachment: dict) -> Element:
    if "content_type" not in attachment:
        return E.image(src=attachment["url"])
    mime = attachment["content_type"]
    if mime.startswith("image/"):
        return E.image(src=attachment["url"], mime=mime, name=attachment.get("filename"), height=attachment.get("height"), width=attachment.get("width"))
    elif mime.startswith("audio/"):
        return E.audio(src=attachment["url"], mime=mime, name=attachment.get("filename"), duration=attachment.get("duration"))
    elif mime.startswith("video/"):
        return E.video(src=attachment["url"], mime=mime, name=attachment.get("filename"), height=attachment.get("height"), width=attachment.get("width"), duration=attachment.get("duration"))
    else:
        return E.file(src=attachment["url"], mime=mime, name=attachment.get("filename"), extra={"size": attachment.get("size")})


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
                result.append(Custom("qq:emoji", {"id": i["id"]}))
    if attachments := event.get("attachments"):
        for i in attachments:
            result.append(_decode_attachment(i))
    if embeds := event.get("embeds"):
        for i in embeds:
            result.append(Custom("qq:embed", i))
    if ark := event.get("ark"):
        result.append(Custom("qq:ark", ark))
    return result
