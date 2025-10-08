from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from satori.element import Custom, E, Element
from satori.model import Channel, ChannelType, Login, MessageObject, User
from satori.parser import Element as RawElement
from satori.parser import parse

from .utils import MilkyNetwork, decode_guild, decode_guild_channel_id, decode_member, get_scene_and_peer, user_avatar

_BASE64_RE = re.compile(r"^data:([\w/.+-]+);base64,")


@dataclass
class State:
    type: Literal["message", "reply", "forward"]
    children: list[dict[str, Any]] = field(default_factory=list)
    author: dict[str, Any] = field(default_factory=dict)


class MilkyMessageEncoder:
    def __init__(self, login: Login, net: MilkyNetwork, channel_id: str):
        self.login = login
        self.net = net
        self.channel_id = channel_id
        self.segments: list[dict[str, Any]] = []
        self.stack = [State("message")]
        self.results: list[MessageObject] = []

    async def send_forward(self):
        if not self.stack[0].children:
            return
        scene, peer_id = get_scene_and_peer(self.channel_id)
        seg = {"type": "forward", "data": {"messages": self.stack[0].children}}
        if scene == "group":
            resp = await self.net.call_api("send_group_message", {"group_id": peer_id, "message": [seg]})
        else:
            resp = await self.net.call_api("send_private_message", {"user_id": peer_id, "message": [seg]})
        if resp:
            channel_type = ChannelType.TEXT if scene == "group" else ChannelType.DIRECT
            channel_id = str(peer_id) if scene == "group" else self.channel_id
            channel = Channel(channel_id, channel_type)
            created_at = datetime.fromtimestamp(resp.get("time", datetime.now().timestamp()))
            message = MessageObject(str(resp.get("message_seq", "")), "", channel=channel, created_at=created_at)
            self.results.append(message)

    async def _send_file(self, attrs: dict[str, Any]):
        uri = attrs.get("src") or attrs.get("url")
        if not uri:
            return
        name = attrs.get("title") or uri.split("/")[-1][:32]
        if match := _BASE64_RE.match(uri):
            uri = f"base64://{uri[len(match.group(0)) :]}"
        scene, peer_id = get_scene_and_peer(self.channel_id)
        if scene == "group":
            await self.net.call_api(
                "upload_group_file",
                {
                    "group_id": peer_id,
                    "file_uri": uri,
                    "file_name": name,
                },
            )
        else:
            await self.net.call_api(
                "upload_private_file",
                {
                    "user_id": peer_id,
                    "file_uri": uri,
                    "file_name": name,
                },
            )
        self.results.append(MessageObject("", ""))

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
        slot = self.stack[0]
        type_, author = slot.type, slot.author
        if not self.segments and "seq" not in author:
            return
        if type_ == "forward":
            if "seq" in author:
                origin = await self.net.call_api(
                    "get_message", {"message_scene": scene, "peer_id": peer_id, "message_seq": author["seq"]}
                )
                segments = origin["message"]["segments"]
                nickname = (
                    origin["message"]["friend"]["nickname"]
                    if scene == "friend"
                    else origin["message"]["group_member"]["nickname"]
                )
                self.stack[1].children.append(
                    {
                        "user_id": origin["message"]["sender_id"],
                        "sender_name": nickname,
                        "segments": await self.sendable(segments),
                    }
                )
            else:
                self.stack[1].children.append(
                    {
                        "user_id": int(author.get("id", self.login.id)),
                        "sender_name": author.get("name", self.login.user.name or self.login.id),
                        "segments": self.segments,
                    }
                )
            self.segments = []
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


async def decode_message(net: MilkyNetwork, payload: dict) -> MessageObject:
    elements = await _decode_segments(net, payload, payload.get("segments") or [])
    guild_id, channel_id = decode_guild_channel_id(payload)
    channel_type = ChannelType.TEXT if guild_id else ChannelType.DIRECT
    channel_name = None
    guild = None
    member = None
    if payload["message_scene"] == "group":
        group_info = payload.get("group")
        if group_info:
            guild = decode_guild(group_info)
            channel_name = group_info.get("group_name")
        member_info = payload.get("group_member")
        if member_info:
            member = decode_member(member_info)
    elif payload["message_scene"] == "friend":
        friend_info = payload.get("friend")
        if friend_info:
            channel_name = friend_info.get("nickname")
    channel = Channel(channel_id, channel_type, channel_name)

    user_name = None
    if payload["message_scene"] == "group":
        member_info = payload.get("group_member")
        if member_info:
            user_name = member_info.get("nickname")
    elif payload["message_scene"] == "friend":
        friend_info = payload.get("friend")
        if friend_info:
            user_name = friend_info.get("nickname")
    user = User(str(payload["sender_id"]), user_name, avatar=user_avatar(payload["sender_id"]))

    message = MessageObject(
        str(payload["message_seq"]),
        "".join(str(elem) for elem in elements),
        channel=channel,
        guild=guild,
        member=member,
        user=user,
        created_at=datetime.fromtimestamp(payload["time"]),
    )
    message.message = elements
    return message


async def _decode_segments(net: MilkyNetwork, payload: dict, segments: Sequence[dict]) -> list[Element]:
    result: list[Element] = []
    for segment in segments:
        seg_type = segment.get("type")
        data = segment.get("data", {})
        if seg_type == "text":
            result.append(E.text(data.get("text", "")))
        elif seg_type == "mention":
            result.append(E.at(str(data.get("user_id"))))
        elif seg_type == "mention_all":
            result.append(E.at_all())
        elif seg_type == "image":
            result.append(E.image(_resource_url(data)))
        elif seg_type == "record":
            result.append(E.audio(_resource_url(data)))
        elif seg_type == "video":
            result.append(E.video(_resource_url(data)))
        elif seg_type == "file":
            result.append(E.file(_resource_url(data)))
        elif seg_type == "reply":
            seq = data.get("message_seq")
            if seq is not None:
                quote = await _decode_reply(net, payload, int(seq))
                if quote:
                    result.append(quote)
        else:
            result.append(Custom(f"milky:{seg_type}", data))
    return result


async def _decode_reply(net: MilkyNetwork, payload: dict, message_seq: int) -> Element | None:
    try:
        response = await net.call_api(
            "get_message",
            {
                "message_scene": payload["message_scene"],
                "peer_id": payload["peer_id"],
                "message_seq": message_seq,
            },
        )
    except Exception:
        return None
    if not response or "message" not in response:
        return None
    quoted = await decode_message(net, response["message"])
    content = []
    if quoted.user:
        content.append(E.author(quoted.user.id, quoted.user.name, quoted.user.avatar))
    content.extend(quoted.message)
    return E.quote(str(message_seq), content=content)


def _resource_url(data: dict) -> str:
    return data.get("temp_url") or data.get("url") or data.get("uri") or ""
