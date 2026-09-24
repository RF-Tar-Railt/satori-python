from collections.abc import Awaitable, Callable

from satori.model import Event, Login

from ..models import MessageItemType, WeixinMessage
from ..network import WxClawNetwork

EventHandler = Callable[[Login, WxClawNetwork, WeixinMessage], Awaitable[Event | None]]

event_handlers: dict[str, EventHandler] = {}


def register_event(event_type: str):
    def wrapper(func: EventHandler):
        event_handlers[event_type] = func
        return func

    return wrapper


def resolve_event_type(msg: WeixinMessage) -> str:
    primary = MessageItemType.TEXT
    for item in msg.item_list or []:
        if item.type in {
            MessageItemType.IMAGE,
            MessageItemType.VOICE,
            MessageItemType.FILE,
            MessageItemType.VIDEO,
        }:
            primary = MessageItemType(item.type)
    return {
        MessageItemType.TEXT: "message.text",
        MessageItemType.IMAGE: "message.image",
        MessageItemType.VOICE: "message.voice",
        MessageItemType.FILE: "message.file",
        MessageItemType.VIDEO: "message.video",
    }[primary]
