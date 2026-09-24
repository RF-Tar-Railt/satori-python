from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import unquote, urlparse

from satori.element import E, Element
from satori.model import Channel, ChannelType, Login, MessageObject, User
from satori.parser import Element as RawElement
from satori.parser import parse

from .models import MessageItem, MessageItemType, TextItem, UploadMediaType
from .network import MediaResource, WxClawNetwork

MARKDOWN_MODIFIERS = {
    "**": {"b", "strong", "bold"},
    "_": {"i", "em", "italic"},
    "`": {"code"},
}


def _escape_markdown(text: str) -> str:
    return re.sub(r"([\\`*_[_~`\]\-(#!>])", r"\\\1", text)


def _media_available(media) -> bool:
    return bool(media and (media.full_url or media.encrypt_query_param) and media.aes_key)


def _cache_media(
    network: WxClawNetwork,
    kind: MessageItemType,
    media,
    *,
    item: MessageItem | None = None,
    title: str | None = None,
    content_type: str | None = None,
) -> str | None:
    if not _media_available(media):
        return None
    return network.cache_media(MediaResource(kind, media, item, title, content_type))


def _decode_primary_item(network: WxClawNetwork, item: MessageItem) -> list[Element]:
    if item.type == MessageItemType.TEXT and item.text_item:
        return [E.text(item.text_item.text or "")]

    if item.type == MessageItemType.IMAGE and item.image_item:
        image = item.image_item
        src = _cache_media(network, MessageItemType.IMAGE, image.media, item=item)
        if not src:
            src = image.url or _cache_media(network, MessageItemType.IMAGE, image.thumb_media)
        return [E.image(src)] if src else []

    if item.type == MessageItemType.VOICE and item.voice_item:
        voice = item.voice_item
        elements: list[Element] = []
        src = _cache_media(network, MessageItemType.VOICE, voice.media, item=item)
        if src:
            duration = voice.playtime / 1000 if voice.playtime is not None else None
            elements.append(E.audio(src, duration=duration))
        if voice.text:
            elements.append(E.text(voice.text))
        return elements

    if item.type == MessageItemType.FILE and item.file_item:
        file = item.file_item
        src = _cache_media(
            network,
            MessageItemType.FILE,
            file.media,
            item=item,
            title=file.file_name,
        )
        return [E.file(src, name=file.file_name)] if src else []

    if item.type == MessageItemType.VIDEO and item.video_item:
        video = item.video_item
        src = _cache_media(network, MessageItemType.VIDEO, video.media, item=item)
        if not src:
            return []
        poster = _cache_media(network, MessageItemType.IMAGE, video.thumb_media)
        return [E.video(src, poster=poster)]

    return []


def decode_elements(network: WxClawNetwork, items: list[MessageItem]) -> list[Element]:
    result: list[Element] = []
    for item in items:
        if item.ref_msg:
            quoted: list[Element] = []
            quote_id: str | None = None
            if item.ref_msg.message_item:
                quote_id = item.ref_msg.message_item.msg_id
                quoted.extend(_decode_primary_item(network, item.ref_msg.message_item))
            if not quoted and item.ref_msg.title:
                quoted.append(E.text(item.ref_msg.title))
            result.append(E.quote(quote_id, content=quoted))
        result.extend(_decode_primary_item(network, item))
    return result


def _filename_from_src(src: str, fallback: str) -> str:
    parsed = urlparse(src)
    filename = unquote(parsed.path.rsplit("/", 1)[-1])
    return filename or fallback


class WxClawMessageEncoder:
    def __init__(
        self,
        login: Login,
        network: WxClawNetwork,
        channel_id: str,
        referrer: dict[str, Any] | None = None,
    ):
        if not channel_id.startswith("private:"):
            raise ValueError("WxClaw only supports direct channels with the 'private:' prefix")
        self.login = login
        self.network = network
        self.channel_id = channel_id
        self.user_id = channel_id.removeprefix("private:")
        if not self.user_id:
            raise ValueError("WxClaw direct channel is missing a user ID")
        self.referrer = referrer or {}
        self.items: list[MessageItem] = []
        self.source_parts: list[str] = []
        self.results: list[MessageObject] = []
        self.use_markdown = False
        self.blockquote_depth = 0
        self.blockquote_line_start = True

    async def send(self, content: str) -> list[MessageObject]:
        await self.render(parse(content))
        await self.flush()
        if not self.results:
            raise ValueError("Message contains no sendable content")
        return self.results

    async def render(self, elements: list[RawElement], *, record: bool = True):
        for element in elements:
            await self.visit(element, record=record)

    def _append_text(self, text: str):
        if not text:
            return
        if self.items and self.items[-1].type == MessageItemType.TEXT and self.items[-1].text_item:
            self.items[-1].text_item.text = (self.items[-1].text_item.text or "") + text
        else:
            self.items.append(MessageItem(type=MessageItemType.TEXT, text_item=TextItem(text=text)))

    def _ensure_markdown(self):
        if self.use_markdown:
            return
        for item in self.items:
            if item.type == MessageItemType.TEXT and item.text_item and item.text_item.text:
                item.text_item.text = _escape_markdown(item.text_item.text)
        self.use_markdown = True

    def _append_content(self, text: str):
        if not text:
            return
        if not self.blockquote_depth:
            self._append_text(text)
            return
        prefix = ">" * self.blockquote_depth + " "
        for char in text:
            if self.blockquote_line_start and char != "\n":
                self._append_text(prefix)
                self.blockquote_line_start = False
            self._append_text(char)
            if char == "\n":
                self.blockquote_line_start = True

    def _reset_markdown(self):
        self.use_markdown = False
        self.blockquote_depth = 0
        self.blockquote_line_start = True

    def _last_text(self) -> str:
        if self.items and self.items[-1].type == MessageItemType.TEXT and self.items[-1].text_item:
            return self.items[-1].text_item.text or ""
        return ""

    async def _append_resource(self, kind: MessageItemType, attrs: dict[str, Any]):
        src = attrs.get("src") or attrs.get("url")
        if not src:
            return
        cached = self.network.get_cached_media(src)
        if kind == MessageItemType.IMAGE and cached and cached.kind == MessageItemType.IMAGE and cached.item:
            image = cached.item.image_item
            if image and image.media:
                self.items.append(MessageItem(type=MessageItemType.IMAGE, image_item=image))
                return

        timeout = attrs.get("timeout")
        timeout_ms = int(timeout) if timeout is not None else None
        content = await self.network.read_resource(src, timeout_ms=timeout_ms)
        upload_type = {
            MessageItemType.IMAGE: UploadMediaType.IMAGE,
            MessageItemType.FILE: UploadMediaType.FILE,
            MessageItemType.VIDEO: UploadMediaType.VIDEO,
        }[kind]
        result = await self.network.prepare_and_upload_file(content, upload_type, self.user_id)
        title = attrs.get("title") or (cached.title if cached else None)
        if kind == MessageItemType.FILE:
            title = title or _filename_from_src(src, "file")
        self.items.append(self.network.build_uploaded_item(kind, result, title=title))

    async def visit(self, element: RawElement, *, record: bool = True):
        type_ = element.type
        attrs = element.attrs
        children = element.children

        if type_ == "message":
            await self.flush()
            if children:
                self.source_parts.extend(str(child) for child in children)
                await self.render(children, record=False)
                await self.flush()
            return
        if type_ in {"quote", "author"}:
            return
        if record:
            self.source_parts.append(str(element))

        if type_ == "text":
            text = attrs.get("text", "")
            self._append_content(_escape_markdown(text) if self.use_markdown else text)
        elif type_ in {"br", "newline"}:
            self._append_content("\n")
        elif type_ in {"p", "paragraph"}:
            if self.items and not self._last_text().endswith("\n"):
                self._append_content("\n")
            await self.render(children, record=False)
            if not self._last_text().endswith("\n"):
                self._append_content("\n")
        elif type_ == "at":
            if attrs.get("type") in {"all", "here"}:
                self._append_content("@all" if attrs.get("type") == "all" else "@here")
            else:
                target = attrs.get("name") or attrs.get("id") or attrs.get("role")
                if target:
                    self._append_content(f"@{target}")
        elif type_ == "sharp":
            target = attrs.get("name") or attrs.get("id")
            if target:
                self._append_content(f"#{target}")
        elif type_ == "a":
            if href := attrs.get("href") or attrs.get("url"):
                self._ensure_markdown()
                self._append_content("[")
                await self.render(children, record=False)
                self._append_content(f"]({href})")
            else:
                await self.render(children, record=False)
        elif type_ == "emoji":
            self._append_content(str(attrs.get("name") or attrs.get("id") or ""))
        elif type_ in {"img", "image"}:
            await self._append_resource(MessageItemType.IMAGE, attrs)
        elif type_ == "file":
            await self._append_resource(MessageItemType.FILE, attrs)
        elif type_ == "video":
            await self._append_resource(MessageItemType.VIDEO, attrs)
        elif type_ == "audio":
            src = attrs.get("src") or attrs.get("url")
            if src:
                title = attrs.get("title")
                self._append_content(f"{title}: {src}" if title else src)
        elif type_ == "button":
            await self.render(children, record=False)
            if href := attrs.get("href"):
                self._append_content(f" ({href})")
        elif type_ == "blockquote":
            self._ensure_markdown()
            if self.items and not self._last_text().endswith("\n"):
                self._append_content("\n")
            self.blockquote_depth += 1
            self.blockquote_line_start = True
            await self.render(children, record=False)
            if not self._last_text().endswith("\n"):
                self._append_content("\n")
            self.blockquote_depth -= 1
            self.blockquote_line_start = True
        else:
            for delimiter, types in MARKDOWN_MODIFIERS.items():
                if type_ in types:
                    self._ensure_markdown()
                    self._append_content(delimiter)
                    await self.render(children, record=False)
                    self._append_content(delimiter)
                    return
            await self.render(children, record=False)

    async def flush(self):
        if not self.items:
            self.source_parts.clear()
            self._reset_markdown()
            return
        client_id = await self.network.send_items(
            self.user_id,
            self.items,
            session_id=str(self.referrer.get("session_id") or ""),
            context_token=str(self.referrer.get("context_token") or ""),
        )
        channel = Channel(self.channel_id, ChannelType.DIRECT)
        self.results.append(
            MessageObject(
                client_id,
                "".join(self.source_parts),
                channel=channel,
                user=User(self.login.id, self.login.user.name, is_bot=True),
                created_at=datetime.now(),
            )
        )
        self.items = []
        self.source_parts = []
        self._reset_markdown()
