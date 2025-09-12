from collections.abc import Awaitable, Callable

from satori.model import Event, Login

from ..utils import OneBotNetwork

events: dict[str, Callable[[Login, OneBotNetwork, dict], Awaitable[Event | None]]] = {}


def register_event(event_type: str):
    def wrapper(func: Callable[[Login, OneBotNetwork, dict], Awaitable[Event | None]]):
        events[event_type] = func
        return func

    return wrapper
