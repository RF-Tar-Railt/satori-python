from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import IntEnum
from typing import Any


class MessageItemType(IntEnum):
    NONE = 0
    TEXT = 1
    IMAGE = 2
    VOICE = 3
    FILE = 4
    VIDEO = 5


class MessageType(IntEnum):
    NONE = 0
    USER = 1
    BOT = 2


class MessageState(IntEnum):
    NEW = 0
    GENERATING = 1
    FINISH = 2


class TypingStatus(IntEnum):
    TYPING = 1
    CANCEL = 2


class UploadMediaType(IntEnum):
    IMAGE = 1
    VIDEO = 2
    FILE = 3
    VOICE = 4


def dump_model(value: Any) -> Any:
    if isinstance(value, IntEnum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: dump_model(field_value)
            for item in fields(value)
            if (field_value := getattr(value, item.name)) is not None
        }
    if isinstance(value, list):
        return [dump_model(item) for item in value]
    if isinstance(value, dict):
        return {key: dump_model(item) for key, item in value.items() if item is not None}
    return value


class ProtocolModel:
    def dump(self) -> dict[str, Any]:
        return dump_model(self)


@dataclass(slots=True)
class CDNMedia(ProtocolModel):
    encrypt_query_param: str | None = None
    aes_key: str | None = None
    encrypt_type: int | None = None
    full_url: str | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any] | None) -> CDNMedia | None:
        if not raw:
            return None
        return cls(
            encrypt_query_param=raw.get("encrypt_query_param"),
            aes_key=raw.get("aes_key"),
            encrypt_type=raw.get("encrypt_type"),
            full_url=raw.get("full_url"),
        )


@dataclass(slots=True)
class TextItem(ProtocolModel):
    text: str | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any] | None) -> TextItem | None:
        return cls(text=raw.get("text")) if raw else None


@dataclass(slots=True)
class ImageItem(ProtocolModel):
    media: CDNMedia | None = None
    thumb_media: CDNMedia | None = None
    aeskey: str | None = None
    url: str | None = None
    mid_size: int | None = None
    thumb_size: int | None = None
    thumb_height: int | None = None
    thumb_width: int | None = None
    hd_size: int | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any] | None) -> ImageItem | None:
        if not raw:
            return None
        return cls(
            media=CDNMedia.parse(raw.get("media")),
            thumb_media=CDNMedia.parse(raw.get("thumb_media")),
            aeskey=raw.get("aeskey"),
            url=raw.get("url"),
            mid_size=raw.get("mid_size"),
            thumb_size=raw.get("thumb_size"),
            thumb_height=raw.get("thumb_height"),
            thumb_width=raw.get("thumb_width"),
            hd_size=raw.get("hd_size"),
        )


@dataclass(slots=True)
class VoiceItem(ProtocolModel):
    media: CDNMedia | None = None
    encode_type: int | None = None
    bits_per_sample: int | None = None
    sample_rate: int | None = None
    playtime: int | None = None
    text: str | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any] | None) -> VoiceItem | None:
        if not raw:
            return None
        return cls(
            media=CDNMedia.parse(raw.get("media")),
            encode_type=raw.get("encode_type"),
            bits_per_sample=raw.get("bits_per_sample"),
            sample_rate=raw.get("sample_rate"),
            playtime=raw.get("playtime"),
            text=raw.get("text"),
        )


@dataclass(slots=True)
class FileItem(ProtocolModel):
    media: CDNMedia | None = None
    file_name: str | None = None
    md5: str | None = None
    len: str | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any] | None) -> FileItem | None:
        if not raw:
            return None
        return cls(
            media=CDNMedia.parse(raw.get("media")),
            file_name=raw.get("file_name"),
            md5=raw.get("md5"),
            len=raw.get("len"),
        )


@dataclass(slots=True)
class VideoItem(ProtocolModel):
    media: CDNMedia | None = None
    video_size: int | None = None
    play_length: int | None = None
    video_md5: str | None = None
    thumb_media: CDNMedia | None = None
    thumb_size: int | None = None
    thumb_height: int | None = None
    thumb_width: int | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any] | None) -> VideoItem | None:
        if not raw:
            return None
        return cls(
            media=CDNMedia.parse(raw.get("media")),
            video_size=raw.get("video_size"),
            play_length=raw.get("play_length"),
            video_md5=raw.get("video_md5"),
            thumb_media=CDNMedia.parse(raw.get("thumb_media")),
            thumb_size=raw.get("thumb_size"),
            thumb_height=raw.get("thumb_height"),
            thumb_width=raw.get("thumb_width"),
        )


@dataclass(slots=True)
class RefMessage(ProtocolModel):
    message_item: MessageItem | None = None
    title: str | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any] | None) -> RefMessage | None:
        if not raw:
            return None
        return cls(
            message_item=MessageItem.parse(raw.get("message_item")),
            title=raw.get("title"),
        )


@dataclass(slots=True)
class MessageItem(ProtocolModel):
    type: int | None = None
    create_time_ms: int | None = None
    update_time_ms: int | None = None
    is_completed: bool | None = None
    msg_id: str | None = None
    ref_msg: RefMessage | None = None
    text_item: TextItem | None = None
    image_item: ImageItem | None = None
    voice_item: VoiceItem | None = None
    file_item: FileItem | None = None
    video_item: VideoItem | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any] | None) -> MessageItem | None:
        if not raw:
            return None
        return cls(
            type=raw.get("type"),
            create_time_ms=raw.get("create_time_ms"),
            update_time_ms=raw.get("update_time_ms"),
            is_completed=raw.get("is_completed"),
            msg_id=raw.get("msg_id"),
            ref_msg=RefMessage.parse(raw.get("ref_msg")),
            text_item=TextItem.parse(raw.get("text_item")),
            image_item=ImageItem.parse(raw.get("image_item")),
            voice_item=VoiceItem.parse(raw.get("voice_item")),
            file_item=FileItem.parse(raw.get("file_item")),
            video_item=VideoItem.parse(raw.get("video_item")),
        )


@dataclass(slots=True)
class WeixinMessage(ProtocolModel):
    seq: int | None = None
    message_id: int | None = None
    from_user_id: str | None = None
    to_user_id: str | None = None
    client_id: str | None = None
    create_time_ms: int | None = None
    update_time_ms: int | None = None
    delete_time_ms: int | None = None
    session_id: str | None = None
    group_id: str | None = None
    message_type: int | None = None
    message_state: int | None = None
    item_list: list[MessageItem] | None = None
    context_token: str | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> WeixinMessage:
        return cls(
            seq=raw.get("seq"),
            message_id=raw.get("message_id"),
            from_user_id=raw.get("from_user_id"),
            to_user_id=raw.get("to_user_id"),
            client_id=raw.get("client_id"),
            create_time_ms=raw.get("create_time_ms"),
            update_time_ms=raw.get("update_time_ms"),
            delete_time_ms=raw.get("delete_time_ms"),
            session_id=raw.get("session_id"),
            group_id=raw.get("group_id"),
            message_type=raw.get("message_type"),
            message_state=raw.get("message_state"),
            item_list=[item for value in raw.get("item_list") or [] if (item := MessageItem.parse(value))],
            context_token=raw.get("context_token"),
        )


@dataclass(slots=True)
class GetUpdatesResponse(ProtocolModel):
    ret: int | None = None
    errcode: int | None = None
    errmsg: str | None = None
    msgs: list[WeixinMessage] | None = None
    get_updates_buf: str | None = None
    longpolling_timeout_ms: int | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> GetUpdatesResponse:
        return cls(
            ret=raw.get("ret"),
            errcode=raw.get("errcode"),
            errmsg=raw.get("errmsg"),
            msgs=[WeixinMessage.parse(item) for item in raw.get("msgs") or []],
            get_updates_buf=raw.get("get_updates_buf"),
            longpolling_timeout_ms=raw.get("longpolling_timeout_ms"),
        )


@dataclass(slots=True)
class GetUploadUrlResponse(ProtocolModel):
    upload_param: str | None = None
    thumb_upload_param: str | None = None
    upload_full_url: str | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> GetUploadUrlResponse:
        return cls(
            upload_param=raw.get("upload_param"),
            thumb_upload_param=raw.get("thumb_upload_param"),
            upload_full_url=raw.get("upload_full_url"),
        )


@dataclass(slots=True)
class GetConfigResponse(ProtocolModel):
    ret: int | None = None
    errmsg: str | None = None
    typing_ticket: str | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> GetConfigResponse:
        return cls(ret=raw.get("ret"), errmsg=raw.get("errmsg"), typing_ticket=raw.get("typing_ticket"))


@dataclass(slots=True)
class QRCodeResponse(ProtocolModel):
    qrcode: str = ""
    qrcode_img_content: str = ""

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> QRCodeResponse:
        return cls(qrcode=raw.get("qrcode", ""), qrcode_img_content=raw.get("qrcode_img_content", ""))


@dataclass(slots=True)
class QRStatusResponse(ProtocolModel):
    status: str = "wait"
    bot_token: str | None = None
    ilink_bot_id: str | None = None
    baseurl: str | None = None
    ilink_user_id: str | None = None
    redirect_host: str | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> QRStatusResponse:
        return cls(
            status=raw.get("status", "wait"),
            bot_token=raw.get("bot_token"),
            ilink_bot_id=raw.get("ilink_bot_id"),
            baseurl=raw.get("baseurl"),
            ilink_user_id=raw.get("ilink_user_id"),
            redirect_host=raw.get("redirect_host"),
        )
