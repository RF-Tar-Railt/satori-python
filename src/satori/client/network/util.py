from typing import Literal, overload

from aiohttp import ClientResponse

from satori.exception import (
    BadRequestException,
    ForbiddenException,
    MethodNotAllowedException,
    NotFoundException,
    ServerException,
    UnauthorizedException,
)
from satori.utils import decode


@overload
async def validate_response(resp: ClientResponse) -> dict: ...


@overload
async def validate_response(resp: ClientResponse, noreturn: Literal[True]) -> None: ...


async def validate_response(resp: ClientResponse, noreturn=False):
    match resp.status:
        case x if 200 <= x < 300:
            if noreturn:
                return
            content = await resp.text()
            return decode(content) if content else {}
        case 400:
            raise BadRequestException(await resp.text())
        case 401:
            raise UnauthorizedException(await resp.text())
        case 403:
            raise ForbiddenException(await resp.text())
        case 404:
            raise NotFoundException(await resp.text())
        case 405:
            raise MethodNotAllowedException(await resp.text())
        case x if x >= 500:
            raise ServerException(await resp.text())
        case _:
            resp.raise_for_status()
