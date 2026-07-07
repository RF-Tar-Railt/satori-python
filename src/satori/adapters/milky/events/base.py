from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime

from satori import EventType
from satori.model import Event, Login, LoginStatus, MessageObject

from ..utils import MilkyNetwork

EventHandler = Callable[[Login, MilkyNetwork, dict], Awaitable[Event | None]]

event_handlers: dict[str, EventHandler] = {}


def register_event(event_type: str):
    def decorator(func: EventHandler):
        event_handlers[event_type] = func
        return func

    return decorator


@register_event("bot_offline")
async def bot_offline(login, net, raw):
    return Event(
        EventType.LOGIN_UPDATED,
        datetime.now(),
        login=Login(
            sn=login.sn,
            platform=login.platform,
            adapter=login.adapter,
            status=LoginStatus.DISCONNECT,
            user=login.user,
            features=login.features.copy(),
        ),
        message=MessageObject("", raw["data"]["reason"]),
    )
