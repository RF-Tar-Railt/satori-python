from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime
from secrets import token_hex
from typing import TYPE_CHECKING, cast

from loguru import _colorama, logger
from loguru._handler import Handler
from loguru._logger import Logger
from loguru._simple_sinks import StreamSink
from nonechat import Backend, Frontend
from nonechat.backend import BotAdd
from nonechat.message import ConsoleMessage
from nonechat.model import DIRECT
from nonechat.model import Event as ConsoleEvent
from nonechat.model import MessageEvent as ConsoleMessageEvent
from nonechat.model import Robot

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
        self.logins = {}
        self.sn = 0
        self._origin_sink: StreamSink | None = None

    def set_adapter(self, adapter: ConsoleAdapter):
        self._adapter = adapter

    def on_console_load(self):
        if self._adapter._logger_id >= 0:
            current_handler: Handler = cast(Logger, logger)._core.handlers[self._adapter._logger_id]
        else:
            current_handler: Handler = list(cast(Logger, logger)._core.handlers.values())[-1]
        if current_handler._colorize and _colorama.should_wrap(self.frontend._fake_output):
            stream = _colorama.wrap(self.frontend._fake_output)
        else:
            stream = self.frontend._fake_output
        self._origin_sink = current_handler._sink
        current_handler._sink = StreamSink(stream)

    async def add_bot(self, bot: Robot):
        if self.storage.add_bot(bot):
            for watcher in self.bot_watchers:
                watcher.post_message(BotAdd(bot))
            login = Login(
                self.sn,
                LoginStatus.ONLINE,
                "console",
                "console",
                User(
                    id=bot.id,
                    name=bot.nickname,
                    avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(bot.avatar):x}.png",
                    is_bot=True,
                ),
                features=["guild.plain"],
            )
            self.sn += 1
            self.logins[bot.id] = login
            await self._adapter.queue.put(Event(EventType.LOGIN_ADDED, datetime.now(), login))

    async def on_console_mount(self):
        logger.success("Console mounted.")

    async def on_console_unmount(self):
        if self._origin_sink is not None:
            if self._adapter._logger_id >= 0:
                current_handler: Handler = cast(Logger, logger)._core.handlers[self._adapter._logger_id]
            else:
                current_handler: Handler = list(cast(Logger, logger)._core.handlers.values())[-1]
            current_handler._sink = self._origin_sink
            self._origin_sink = None
        for login in self.logins.values():
            login.status = LoginStatus.OFFLINE
            await self._adapter.queue.put(
                Event(
                    EventType.LOGIN_REMOVED,
                    datetime.now(),
                    login,
                )
            )

        logger.success("Console exit.")
        logger.warning("Press Ctrl-C for Application exit")

    async def post_event(self, event: ConsoleEvent):
        if event.self_id not in self.logins:
            logger.warning(f"Received event from unknown bot: {event.self_id}")
            return
        user = User(
            event.user.id,
            event.user.nickname,
            avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(event.user.avatar):x}.png",
        )
        member = Member(user, nick=user.name, avatar=user.avatar)
        if isinstance(event, ConsoleMessageEvent):
            message = MessageObject(token_hex(8), handle_message(event.message))
            if event.channel == DIRECT:
                await self._adapter.queue.put(
                    Event(
                        EventType.MESSAGE_CREATED,
                        event.time,
                        self.logins[event.self_id],
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
                        self.logins[event.self_id],
                        user=user,
                        member=member,
                        channel=channel,
                        guild=guild,
                        message=message,
                    )
                )
        else:
            await self._adapter.queue.put(
                Event(
                    EventType.INTERNAL,
                    event.time,
                    self.logins[event.self_id],
                    _type=event.type,
                    _data=asdict(event),
                )
            )
