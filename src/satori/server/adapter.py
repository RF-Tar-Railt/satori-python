from abc import abstractmethod
from typing import Any, AsyncIterator, Callable, Dict, List, Union

from launart import Service

from ..const import Api
from ..model import Event, Login
from .route import RouteCall, RouterMixin


class Adapter(Service, RouterMixin):
    routes: Dict[str, RouteCall[Any, Any]]

    @abstractmethod
    def get_platform(self) -> str: ...

    @abstractmethod
    def publisher(self) -> AsyncIterator[Event]: ...

    @abstractmethod
    def validate_headers(self, headers: Dict[str, Any]) -> bool: ...

    @abstractmethod
    def authenticate(self, token: str) -> bool: ...

    @abstractmethod
    async def get_logins(self) -> List[Login]: ...

    def _route(self, path: Union[str, Api]) -> Callable[[RouteCall], RouteCall]:
        def wrapper(func: RouteCall):
            if isinstance(path, str):
                self.routes[f"internal/{path}"] = func
            else:
                self.routes[str(path.value)] = func
            return func

        return wrapper

    def __init__(self):
        super().__init__()
        self.routes = {}

    @property
    def id(self):
        return f"satori-python.adapter.{self.get_platform()}#{id(self)}"
