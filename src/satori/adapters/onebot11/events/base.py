from collections.abc import Awaitable
from typing import Callable, Optional

from satori.model import Event, Login

from ..utils import OneBotNetwork

events: dict[str, Callable[[Login, OneBotNetwork, dict], Awaitable[Optional[Event]]]] = {}


def register_event(event_type: str):
    def wrapper(func: Callable[[Login, OneBotNetwork, dict], Awaitable[Optional[Event]]]):
        events[event_type] = func
        return func

    return wrapper
