import json
from typing import Literal, overload

from aiohttp import ClientResponse

from satori.exception import (
    ApiNotImplementedException,
    BadRequestException,
    ForbiddenException,
    MethodNotAllowedException,
    NotFoundException,
    UnauthorizedException,
)


@overload
async def validate_response(resp: ClientResponse) -> dict: ...


@overload
async def validate_response(resp: ClientResponse, noreturn: Literal[True]) -> None: ...


async def validate_response(resp: ClientResponse, noreturn=False):
    if 200 <= resp.status < 300:
        return json.loads(content) if (content := await resp.text()) else {}
    elif resp.status == 400:
        raise BadRequestException(await resp.text())
    elif resp.status == 401:
        raise UnauthorizedException(await resp.text())
    elif resp.status == 403:
        raise ForbiddenException(await resp.text())
    elif resp.status == 404:
        raise NotFoundException(await resp.text())
    elif resp.status == 405:
        raise MethodNotAllowedException(await resp.text())
    elif resp.status == 500:
        raise ApiNotImplementedException(await resp.text())
    else:
        resp.raise_for_status()
        if not noreturn:
            return
        return json.loads(content) if (content := await resp.text()) else {}
