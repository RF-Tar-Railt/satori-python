from __future__ import annotations

from collections.abc import Awaitable, Callable

from satori.model import Event, Login

from ..utils import MilkyNetwork

EventHandler = Callable[[Login, MilkyNetwork, dict], Awaitable[Event | None]]

event_handlers: dict[str, EventHandler] = {}


def register_event(event_type: str):
    def decorator(func: EventHandler):
        event_handlers[event_type] = func
        return func

    return decorator
