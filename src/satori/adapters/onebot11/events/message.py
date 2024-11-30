from __future__ import annotations

from datetime import datetime

from satori import EventType
from satori.model import Channel, ChannelType, Event, Guild, LoginPreview, Member, MessageObject, User

from ..message import decode
from ..utils import GROUP_AVATAR_URL, USER_AVATAR_URL, OneBotNetwork
from .base import register_event

#     @m.entity(OneBot11Capability.event_callback, raw_event="message.private.group")
#     async def private_group(self, raw_event: dict):
#         self_id = raw_event["self_id"]
#         account = self.connection.accounts.get(self_id)
#         if account is None:
#             logger.warning(f"Unknown account {self_id} received message {raw_event}")
#             return
#         group = Selector().land(account.route["land"]).group(str(raw_event["sender"]["group_id"]))
#         # 好像 ob11 本来没这个字段, 但 gocq 是有的, 不过嘛, 管他呢
#         member = group.member(str(raw_event["sender"]["user_id"]))
#         context = Context(
#             account,
#             member,
#             member,
#             member,
#             group.member(str(raw_event["self_id"])),
#         )
#         message = await OneBot11Capability(account.staff.ext({"context": context})).deserialize_chain(
#             raw_event["message"]
#         )
#         reply = None
#         if i := message.get(Reference):
#             reply = i[0].message
#             message = message.exclude(Reference)
#         return MessageReceived(
#             context,
#             Message(
#                 id=raw_event["message_id"],
#                 scene=member,
#                 sender=member,
#                 content=message,
#                 time=datetime.fromtimestamp(raw_event["time"]),
#                 reply=reply,
#             ),
#         )
#
#     @m.entity(OneBot11Capability.event_callback, raw_event="message.private.other")
#     async def private_other(self, raw_event: dict):
#         self_id = raw_event["self_id"]
#         account = self.connection.accounts.get(self_id)
#         if account is None:
#             logger.warning(f"Unknown account {self_id} received message {raw_event}")
#             return
#         stranger = Selector().land(account.route["land"]).stranger(str(raw_event["sender"]["user_id"]))
#         context = Context(
#             account,
#             stranger,
#             stranger,
#             stranger,
#             Selector().land(account.route["land"]).account(str(raw_event["self_id"])),
#         )
#         message = await OneBot11Capability(account.staff.ext({"context": context})).deserialize_chain(
#             raw_event["message"]
#         )
#         reply = None
#         if i := message.get(Reference):
#             reply = i[0].message
#             message = message.exclude(Reference)
#         return MessageReceived(
#             context,
#             Message(
#                 id=raw_event["message_id"],
#                 scene=stranger,
#                 sender=stranger,
#                 content=message,
#                 time=datetime.fromtimestamp(raw_event["time"]),
#                 reply=reply,
#             ),
#         )
#
#
#     @m.entity(OneBot11Capability.event_callback, raw_event="message_sent.group.normal")
#     async def message_sent(self, raw_event: dict):
#         self_id = raw_event["self_id"]
#         account = self.connection.accounts.get(self_id)
#         if account is None:
#             logger.warning(f"Unknown account {self_id} sent message {raw_event}")
#             return
#
#         group = Selector().land(account.route["land"]).group(str(raw_event["group_id"]))
#         member = group.member(str(raw_event["user_id"]))
#         context = Context(account, member, group, group, member)
#         message = await OneBot11Capability(account.staff.ext({"context": context})).deserialize_chain(
#             raw_event["message"]
#         )
#         reply = None
#         if i := message.get(Reference):
#             reply = i[0].message
#             message = message.exclude(Reference)
#         return MessageSent(
#             context,
#             Message(
#                 str(raw_event["message_id"]),
#                 group,
#                 member,
#                 message,
#                 datetime.fromtimestamp(raw_event["time"]),
#                 reply,
#             ),
#             account,
#         )
#


@register_event("message.private.friend")
async def private_friend(login: LoginPreview, net: OneBotNetwork, raw: dict):
    sender: dict = raw["sender"]
    user = User(str(sender["user_id"]), sender["nickname"], USER_AVATAR_URL.format(uin=sender["user_id"]))
    channel = Channel(f"private:{sender['user_id']}", ChannelType.DIRECT, sender["nickname"])
    return Event(
        0,
        EventType.MESSAGE_CREATED,
        datetime.now(),
        login=login,
        user=user,
        channel=channel,
        message=MessageObject(str(raw["message_id"]), await decode(raw["message"], net)),
    )


@register_event("notice.friend_recall")
async def friend_message_recall(login: LoginPreview, net: OneBotNetwork, raw: dict):
    sender: dict = raw["sender"]
    user = User(str(sender["user_id"]), sender["nickname"], USER_AVATAR_URL.format(uin=sender["user_id"]))
    channel = Channel(f"private:{sender['user_id']}", ChannelType.DIRECT, sender["nickname"])
    return Event(
        0,
        EventType.MESSAGE_DELETED,
        datetime.now(),
        login=login,
        user=user,
        channel=channel,
        message=MessageObject(str(raw["message_id"]), ""),
    )


@register_event("message.group.normal")
@register_event("message.group.notice")
async def group(login: LoginPreview, net: OneBotNetwork, raw: dict):
    sender: dict = raw["sender"]
    user = User(str(sender["user_id"]))
    member = Member(user, sender["nickname"], USER_AVATAR_URL.format(uin=sender["user_id"]))
    guild = Guild(str(raw["group_id"]), avatar=GROUP_AVATAR_URL.format(group=raw["group_id"]))
    channel = Channel(str(raw["group_id"]), ChannelType.TEXT)
    return Event(
        0,
        EventType.MESSAGE_CREATED,
        datetime.now(),
        login=login,
        user=user,
        guild=guild,
        channel=channel,
        member=member,
        message=MessageObject(str(raw["message_id"]), await decode(raw["message"], net)),
    )


@register_event("notice.group_recall")
async def group_message_recall(login: LoginPreview, net: OneBotNetwork, raw: dict):
    sender: dict = raw["sender"]
    user = User(str(sender["user_id"]))
    member = Member(user, sender["nickname"], USER_AVATAR_URL.format(uin=sender["user_id"]))
    guild = Guild(str(raw["group_id"]), avatar=GROUP_AVATAR_URL.format(group=raw["group_id"]))
    channel = Channel(str(raw["group_id"]), ChannelType.TEXT)
    operator = User(str(raw["operator_id"]))
    return Event(
        0,
        EventType.MESSAGE_DELETED,
        datetime.now(),
        login=login,
        user=user,
        guild=guild,
        channel=channel,
        member=member,
        operator=operator,
        message=MessageObject(str(raw["message_id"]), ""),
    )
