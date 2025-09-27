from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from satori.element import Custom, E, Element
from satori.model import Channel, ChannelType, Login, MessageObject, User
from satori.parser import Element as RawElement
from satori.parser import parse

from .utils import MilkyNetwork, decode_guild, decode_guild_channel_id, decode_member, get_scene_and_peer, user_avatar

_BASE64_RE = re.compile(r"^data:([\w/.+-]+);base64,")


class MilkyMessageEncoder:
    def __init__(self, login: Login, net: MilkyNetwork, channel_id: str):
        self.login = login
        self.net = net
        self.channel_id = channel_id
        self.segments: list[dict[str, Any]] = []
        self.elements: list[Element] = []
        self.results: list[MessageObject] = []

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
            self.elements.append(E.text(text))
        elif type_ == "br":
            if not self.segments or self.segments[-1]["type"] != "text":
                self.segments.append({"type": "text", "data": {"text": "\n"}})
            else:
                self.segments[-1]["data"]["text"] += "\n"
            self.elements.append(E.text("\n"))
        elif type_ == "p":
            await self.render(children)
            if self.segments:
                if self.segments[-1]["type"] == "text":
                    self.segments[-1]["data"]["text"] += "\n"
                else:
                    self.segments.append({"type": "text", "data": {"text": "\n"}})
            self.elements.append(E.text("\n"))
        elif type_ == "at":
            if attrs.get("type") == "all":
                self.segments.append({"type": "mention_all", "data": {}})
                self.elements.append(E.at_all())
            elif "id" in attrs:
                target = attrs["id"]
                self.segments.append({"type": "mention", "data": {"user_id": int(target)}})
                self.elements.append(E.at(str(target)))
        elif type_ == "quote":
            quote_id = attrs.get("id")
            if quote_id is not None:
                try:
                    seq = int(quote_id)
                except ValueError:
                    seq = None
                if seq is not None:
                    self.segments.append({"type": "reply", "data": {"message_seq": seq}})
                    self.elements.append(E.quote(str(seq), content=[E.text("")]))
            await self.render(children)
        elif type_ in {"img", "image"}:
            uri = attrs.get("src") or attrs.get("url")
            if not uri:
                return
            if match := _BASE64_RE.match(uri):
                uri = f"base64://{uri[len(match.group(0)) :]}"
            self.segments.append({"type": "image", "data": {"uri": uri, "sub_type": attrs.get("sub_type", "normal")}})
            self.elements.append(E.image(uri))
        elif type_ == "audio":
            uri = attrs.get("src") or attrs.get("url")
            if not uri:
                return
            if match := _BASE64_RE.match(uri):
                uri = f"base64://{uri[len(match.group(0)) :]}"
            self.segments.append({"type": "record", "data": {"uri": uri}})
            self.elements.append(E.audio(uri))
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
            self.elements.append(E.video(uri))
        else:
            await self.render(children)

    async def flush(self):
        if not self.segments:
            return
        scene, peer_id = get_scene_and_peer(self.channel_id)
        payload = {"message": self.segments}
        if scene == "group":
            payload["group_id"] = peer_id
            resp = await self.net.call_api("send_group_message", payload)
        else:
            payload["user_id"] = peer_id
            resp = await self.net.call_api("send_private_message", payload)
        if resp:
            channel_type = ChannelType.TEXT if scene == "group" else ChannelType.DIRECT
            channel_id = str(peer_id) if scene == "group" else self.channel_id
            channel = Channel(channel_id, channel_type)
            created_at = datetime.fromtimestamp(resp.get("time", datetime.now().timestamp()))
            content = "".join(str(elem) for elem in self.elements)
            message = MessageObject(str(resp.get("message_seq", "")), content, channel=channel, created_at=created_at)
            message.message = list(self.elements)
            self.results.append(message)
        self.segments = []
        self.elements = []


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
