from collections.abc import Awaitable, Callable

from satori.model import Event, Login

from ..utils import MilkyNetwork

events: dict[str, Callable[[Login, MilkyNetwork, dict], Awaitable[Event | None]]] = {}


def register_event(event_type: str):
    def wrapper(func: Callable[[Login, MilkyNetwork, dict], Awaitable[Event | None]]):
        events[event_type] = func
        return func

    return wrapper