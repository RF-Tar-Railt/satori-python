from __future__ import annotations

import re
import sys
from dataclasses import asdict
from datetime import datetime
from secrets import token_hex
from typing import TYPE_CHECKING

from loguru import logger
from nonechat import Backend, Frontend
from nonechat.message import ConsoleMessage
from nonechat.model import DIRECT
from nonechat.model import Event as ConsoleEvent
from nonechat.model import MessageEvent as ConsoleMessageEvent

from satori.const import EventType
from satori.event import Event
from satori.model import Channel, ChannelType, Guild, Login, LoginStatus, Member, MessageObject, User

if TYPE_CHECKING:
    from .main import ConsoleAdapter


def handle_message(message: ConsoleMessage) -> str:
    content = str(message)
    content = re.sub(r"@(\w+)", r"@<at id='\1'>", content)  # Handle mentions
    return content


class SatoriConsoleBackend(Backend):
    _adapter: ConsoleAdapter

    def __init__(self, app: Frontend):
        super().__init__(app)
        self._stderr = sys.stdout
        self._logger_id: int | None = None
        self._should_restore_logger: bool = False
        self.login = Login(
            0,
            LoginStatus.OFFLINE,
            "console",
            "console",
            User(
                id=self.bot.id,
                name=self.bot.nickname,
                avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(self.bot.avatar):x}.png",
                is_bot=True,
            ),
            features=["guild.plain"],
        )

    def set_adapter(self, adapter: ConsoleAdapter):
        self._adapter = adapter

    def on_console_load(self):
        logger.remove()
        self._should_restore_logger = True
        self._logger_id = logger.add(self.frontend._fake_output, level=0, diagnose=False)

    def on_console_mount(self):
        logger.success("Console mounted.")
        self.login.status = LoginStatus.ONLINE
        self._adapter.queue.put_nowait(
            Event(
                EventType.LOGIN_ADDED,
                datetime.now(),
                self.login,
            )
        )

    def on_console_unmount(self):
        if self._logger_id is not None:
            logger.remove(self._logger_id)
            self._logger_id = None
        if self._should_restore_logger:
            logger.add(
                self._stderr,
                backtrace=True,
                diagnose=True,
                colorize=True,
            )
            self._should_restore_logger = False
        self.login.status = LoginStatus.OFFLINE
        self._adapter.queue.put_nowait(
            Event(
                EventType.LOGIN_REMOVED,
                datetime.now(),
                self.login,
            )
        )
        logger.success("Console exit.")
        logger.warning("Press Ctrl-C for Application exit")

    async def post_event(self, event: ConsoleEvent):
        user = User(
            event.user.id,
            event.user.nickname,
            avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(event.user.avatar):x}.png",
        )
        member = Member(user, nick=user.nick, avatar=user.avatar)
        if isinstance(event, ConsoleMessageEvent):
            message = MessageObject(token_hex(8), handle_message(event.message))
            if event.channel == DIRECT:
                await self._adapter.queue.put(
                    Event(
                        EventType.MESSAGE_CREATED,
                        event.time,
                        self.login,
                        user=user,
                        channel=Channel(
                            id=f"private:{user.id}",
                            type=ChannelType.DIRECT,
                            name=user.name,
                        ),
                        message=message,
                    )
                )
            else:
                guild = Guild(
                    id=event.channel.id,
                    name=event.channel.name,
                    avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(event.channel.avatar):x}.png",
                )
                channel = Channel(
                    id=event.channel.id,
                    type=ChannelType.TEXT,
                    name=event.channel.name,
                )
                await self._adapter.queue.put(
                    Event(
                        EventType.MESSAGE_CREATED,
                        event.time,
                        self.login,
                        user=user,
                        member=member,
                        channel=channel,
                        guild=guild,
                        message=message,
                    )
                )
        else:
            await self._adapter.queue.put(
                Event(EventType.INTERNAL, event.time, self.login, _type=event.type, _data=asdict(event))
            )
