from collections.abc import Awaitable, Callable

from satori.model import Event, Login

from ..utils import Payload, QQBotNetwork

EventHandler = Callable[[Login, Login, QQBotNetwork, Payload], Awaitable[Event | None]]

event_handlers: dict[str, EventHandler] = {}


def register_event(event_type: str):
    def wrapper(func: EventHandler):
        event_handlers[event_type] = func
        return func

    return wrapper
