from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from loguru import logger

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
        name = attrs.get("title") or uri.split("/")[-1]
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
        match type_:
            case "text":
                text = attrs.get("text", "")
                if not self.segments or self.segments[-1]["type"] != "text":
                    self.segments.append({"type": "text", "data": {"text": text}})
                else:
                    self.segments[-1]["data"]["text"] += text
            case "br":
                if not self.segments or self.segments[-1]["type"] != "text":
                    self.segments.append({"type": "text", "data": {"text": "\n"}})
                else:
                    self.segments[-1]["data"]["text"] += "\n"
            case "p":
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
            case "at":
                if attrs.get("type") == "all":
                    self.segments.append({"type": "mention_all", "data": {}})
                elif "id" in attrs:
                    target = attrs["id"]
                    self.segments.append({"type": "mention", "data": {"user_id": int(target)}})
            case "sharp":
                self.segments.append({"type": "text", "data": {"text": attrs["id"]}})
            case "a":
                await self.render(children)
                if "href" in attrs:
                    if not self.segments or self.segments[-1]["type"] != "text":
                        self.segments.append({"type": "text", "data": {"text": f" ({attrs['href']})"}})
                    else:
                        self.segments[-1]["data"]["text"] += f" ({attrs['href']})"
            case "img" | "image":
                uri = attrs.get("src") or attrs.get("url")
                if not uri:
                    return
                if match := _BASE64_RE.match(uri):
                    uri = f"base64://{uri[len(match.group(0)) :]}"
                sub_type = "normal"
                for t in ("sub_type", "subType", "milky:sub-type", "milky:subType"):
                    if t in attrs:
                        sub_type = attrs[t]
                        break
                summary = None
                for t in ("summary", "alt", "milky:summary", "title"):
                    if t in attrs:
                        summary = attrs[t]
                        break
                self.segments.append(
                    {
                        "type": "image",
                        "data": {"uri": uri, "sub_type": sub_type, "summary": summary},
                    }
                )
            case "audio":
                uri = attrs.get("src") or attrs.get("url")
                if not uri:
                    return
                if match := _BASE64_RE.match(uri):
                    uri = f"base64://{uri[len(match.group(0)) :]}"
                self.segments.append({"type": "record", "data": {"uri": uri}})
            case "video":
                uri = attrs.get("src") or attrs.get("url")
                if not uri:
                    return
                if match := _BASE64_RE.match(uri):
                    uri = f"base64://{uri[len(match.group(0)) :]}"
                payload = {"uri": uri}
                if poster := attrs.get("poster"):
                    payload["thumb_uri"] = poster
                self.segments.append({"type": "video", "data": payload})
            case "milky:face" | "emoji":
                if ":" in attrs["id"]:
                    _, emj_id_str = attrs["id"].split(":", 1)
                    emj_id = emj_id_str
                else:
                    emj_id = attrs["id"]
                is_large = attrs.get("milky:is-large") or attrs.get("milky:isLarge") or attrs.get("isLarge") or False
                self.segments.append({"type": "face", "data": {"face_id": emj_id, "is_large": is_large}})
            case "file":
                await self.flush()
                await self._send_file(attrs)
            case "milky:light_app":
                await self.flush()
                self.segments.append(
                    {"type": "light_app", "data": {"json_payload": attrs.get("json_payload", attrs["jsonPayload"])}}
                )
            case "markdown" | "milky:markdown":
                await self.flush()
                self.segments.append({"type": "markdown", "data": {"content": str(children[0])}})
            case "author":
                self.stack[0].author.update(attrs)
            case "quote":
                await self.flush()
                self.segments.append({"type": "reply", "data": {"message_seq": int(attrs["id"])}})
            case "message":
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
                        payload["id"] = int(attrs.get("user_id", attrs["userId"]))
                    if "time" in attrs:
                        payload["time"] = int(attrs["time"])
                    self.stack[0].author.update(payload)
                    await self.render(children)
                    await self.flush()
            case _:
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
                        "time": origin["message"]["time"],
                    }
                )
            else:
                self.stack[1].children.append(
                    {
                        "user_id": int(author.get("id", self.login.id)),
                        "sender_name": author.get("name", self.login.user.name or self.login.id),
                        "segments": self.segments,
                        "time": int(author.get("time", datetime.now().timestamp())),
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
        seg_type: str | None = segment.get("type")
        data: dict = segment.get("data", {})
        match seg_type:
            case "text":
                result.append(E.text(data.get("text", "")))
            case "mention":
                result.append(E.at(str(data.get("user_id")), name=data.get("name")))
            case "mention_all":
                result.append(E.at_all())
            case "face":
                result.append(
                    E.emoji.unpack({"id": str(data.get("face_id")), "milky:is-large": data.get("is_large", False)})
                )
            case "image":
                result.append(
                    E.image(
                        await _resource_url(net, data),
                        width=data.get("width", None),
                        height=data.get("height", None),
                        extra={"milky:subType": data.get("sub_type"), "milky:summary": data.get("summary")},
                    )
                )
            case "record":
                result.append(
                    E.audio(
                        await _resource_url(net, data),
                        duration=float(data.get("duration", 0)),
                    )
                )
            case "video":
                result.append(
                    E.video(
                        await _resource_url(net, data),
                        width=data.get("width", None),
                        height=data.get("height", None),
                        duration=float(data.get("duration", 0)),
                    )
                )
            case "file":
                if payload["message_scene"] == "group":
                    url = (
                        await net.call_api(
                            "get_group_file_download_url",
                            {"group_id": payload["peer_id"], "file_id": data.get("file_id")},
                        )
                    )["download_url"]
                else:
                    url = (
                        await net.call_api(
                            "get_private_file_download_url",
                            {
                                "user_id": payload["peer_id"],
                                "file_id": data.get("file_id"),
                                "file_hash": data.get("file_hash"),
                            },
                        )
                    )["download_url"]
                result.append(
                    E.file(
                        url,
                        name=data.get("file_name", None),
                        extra={"milky:fileSize": data.get("file_size"), "milky:fileHash": data.get("file_hash")},
                    )
                )
            case "reply":
                seq = data.get("message_seq")
                if seq is not None:
                    quote = await _decode_reply(net, payload, data, int(seq))
                    if quote:
                        result.append(quote)
            case "forward":
                forward_id = data.get("forward_id")
                if forward_id is not None:
                    if not net.fetch_forward_message:
                        result.append(E.message(forward_id, content=[], forward=True))
                        continue
                    try:
                        messages = (await net.call_api("get_forwarded_messages", {"forward_id": forward_id}))[
                            "messages"
                        ]
                    except Exception as e:
                        logger.error(
                            f"Failed to fetch forwarded messages for forward_id {forward_id}: {payload}", exc_info=e
                        )
                        messages = []
                    forward_elements = []
                    for msg in messages:
                        sender_name = msg.get("sender_name")
                        avatar = msg.get("avatar_url")
                        response = {}
                        if "message_seq" in msg:
                            try:
                                response = await net.call_api(
                                    "get_message",
                                    {
                                        "message_scene": payload["message_scene"],
                                        "peer_id": payload["peer_id"],
                                        "message_seq": msg["message_seq"],
                                    },
                                )
                            except Exception as e:
                                logger.error(
                                    f"Failed to fetch message {msg['message_seq']} for forward: {payload}", exc_info=e
                                )
                                pass
                        if response:
                            origin = await decode_message(net, response["message"])
                            content = []
                            if origin.user:
                                content.append(
                                    E.author(
                                        origin.user.id, origin.user.name or sender_name, origin.user.avatar or avatar
                                    )
                                )
                            content.extend(origin.message)
                        else:
                            content = await _decode_segments(net, payload, msg.get("segments", []))
                            content.insert(0, E.author(str(msg.get("sender_id")), sender_name, avatar))
                        forward_elements.append(E.message(str(msg.get("message_seq")), content=content))
                    result.append(E.message(forward_id, content=forward_elements, forward=True))
            case _:
                elem = Custom(f"milky:{seg_type}", data)
                if seg_type == "market_face":
                    elem.children.append(
                        E.image(data["url"], extra={"milky:subType": "sticker", "milky:summary": data.get("summary")})
                    )
                result.append(elem)
    return result


async def _decode_reply(net: MilkyNetwork, payload: dict, data: dict, message_seq: int) -> Element | None:
    if all(k in data for k in ("sender_id", "time", "segments")):
        user = User(str(data["sender_id"]), data.get("sender_name"), avatar=user_avatar(data["sender_id"]))
        elements = await _decode_segments(net, payload, data["segments"])
        content = []
        if user:
            content.append(E.author(user.id, user.name, user.avatar))
        content.extend(elements)
        return E.quote(str(message_seq), content=content)
    try:
        response = await net.call_api(
            "get_message",
            {
                "message_scene": payload["message_scene"],
                "peer_id": payload["peer_id"],
                "message_seq": message_seq,
            },
        )
    except Exception as e:
        logger.error(f"Failed to fetch message {message_seq} for reply: {payload}", exc_info=e)
        return None
    if not response or "message" not in response:
        return None
    quoted = await decode_message(net, response["message"])
    content = []
    if quoted.user:
        content.append(E.author(quoted.user.id, quoted.user.name, quoted.user.avatar))
    content.extend(quoted.message)
    return E.quote(str(message_seq), content=content)


async def _resource_url(net: MilkyNetwork, data: dict) -> str:
    if "uri" in data:
        return data["uri"]
    if "url" in data:
        return data["url"]
    if "temp_url" in data:
        return data["temp_url"]
    if "resource_id" in data:
        return (await net.call_api("get_resource_temp_url", {"resource_id": data["resource_id"]}))["url"]
    return ""
