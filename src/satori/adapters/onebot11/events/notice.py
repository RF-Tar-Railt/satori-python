# from __future__ import annotations
#
# from datetime import timedelta
# from typing import cast
#
# from loguru import logger
#
# from avilla.core.context import Context
# from avilla.core.event import (
#     DirectSessionCreated,
#     MetadataModified,
#     ModifyDetail,
#     SceneCreated,
#     SceneDestroyed,
#     MemberCreated,
#     MemberDestroyed,
# )
# from avilla.core.selector import Selector
# from avilla.onebot.v11.capability import OneBot11Capability
# from avilla.onebot.v11.collector.connection import ConnectionCollector
# from avilla.standard.core.activity import ActivityTrigged
# from avilla.standard.core.privilege import MuteInfo, Privilege
# from avilla.standard.core.file import FileReceived
# from avilla.standard.qq.event import PocketLuckyKingNoticed
# from avilla.standard.qq.honor import Honor
#
#
# class OneBot11EventNoticePerform((m := ConnectionCollector())._):
#     m.namespace = "avilla.protocol/onebot11::event"
#     m.identify = "notice"


#
#     @m.entity(OneBot11Capability.event_callback, raw_event="notice.group_ban.ban")
#     async def member_muted(self, raw_event: dict):
#         self_id = raw_event["self_id"]
#         account = self.connection.accounts.get(self_id)
#         if account is None:
#             logger.warning(f"Unknown account {self_id} received message {raw_event}")
#             return
#         group = Selector().land("qq").group(str(raw_event["group_id"]))
#         endpoint = group.member(str(raw_event["user_id"]))
#         operator = group.member(str(raw_event["operator_id"]))
#         context = Context(
#             account,
#             operator,
#             endpoint,
#             group,
#             group.member(str(self_id)),
#         )
#         return MetadataModified(
#             context,
#             endpoint,
#             MuteInfo,
#             {
#                 MuteInfo.inh().muted: ModifyDetail("set", True),
#                 MuteInfo.inh().duration: ModifyDetail("set", timedelta(seconds=raw_event["duration"])),
#             },
#             operator=operator,
#             scene=group,
#         )
#
#     @m.entity(OneBot11Capability.event_callback, raw_event="notice.group_ban.lift_ban")
#     async def member_unmuted(self, raw_event: dict):
#         self_id = raw_event["self_id"]
#         account = self.connection.accounts.get(self_id)
#         if account is None:
#             logger.warning(f"Unknown account {self_id} received message {raw_event}")
#             return
#         group = Selector().land("qq").group(str(raw_event["group_id"]))
#         endpoint = group.member(str(raw_event["user_id"]))
#         operator = group.member(str(raw_event["operator_id"]))
#         context = Context(
#             account,
#             operator,
#             endpoint,
#             group,
#             group.member(str(self_id)),
#         )
#         return MetadataModified(
#             context,
#             endpoint,
#             MuteInfo,
#             {
#                 MuteInfo.inh().muted: ModifyDetail("clear"),
#                 MuteInfo.inh().duration: ModifyDetail("clear"),
#             },
#             operator=operator,
#             scene=group,
#         )
#
#     @m.entity(OneBot11Capability.event_callback, raw_event="notice.friend_add")
#     async def friend_add(self, raw_event: dict):
#         self_id = raw_event["self_id"]
#         account = self.connection.accounts.get(self_id)
#         if account is None:
#             logger.warning(f"Unknown account {self_id} received message {raw_event}")
#             return
#         friend = Selector().land("qq").friend(str(raw_event["user_id"]))
#         context = Context(account, friend, friend, friend, account.route)
#         return DirectSessionCreated(context)
#
#     @m.entity(OneBot11Capability.event_callback, raw_event="notice.notify.poke")
#     async def nudge_received(self, raw_event: dict):
#         self_id = raw_event["self_id"]
#         account = self.connection.accounts.get(self_id)
#         if account is None:
#             logger.warning(f"Unknown account {self_id} sent message {raw_event}")
#             return
#         if "group_id" in raw_event:
#             group = Selector().land(account.route["land"]).group(str(raw_event["group_id"]))
#             target = group.member(str(raw_event["target_id"]))
#             operator = group.member(str(raw_event["user_id"]))
#             context = Context(account, operator, target, group, group.member(str(self_id)))
#             return ActivityTrigged(context, "nudge", group, target.nudge("_"), operator)
#         else:
#             friend = Selector().land(account.route["land"]).friend(str(raw_event["sender_id"]))
#             selft = account.route
#             context = Context(account, friend, selft, friend, selft)
#             return ActivityTrigged(context, "nudge", friend, friend.nudge("_"), friend)
#
#     @m.entity(OneBot11Capability.event_callback, raw_event="notice.notify.lucky_king")
#     async def lucky_king_received(self, raw_event: dict):
#         self_id = raw_event["self_id"]
#         account = self.connection.accounts.get(self_id)
#         if account is None:
#             logger.warning(f"Unknown account {self_id} sent message {raw_event}")
#             return
#
#         group = Selector().land(account.route["land"]).group(str(raw_event["group_id"]))
#         target = group.member(str(raw_event["target_id"]))
#         operator = group.member(str(raw_event["user_id"]))
#         context = Context(account, operator, target, group, group.member(str(self_id)))
#         return PocketLuckyKingNoticed(context)
#
#     @m.entity(OneBot11Capability.event_callback, raw_event="notice.notify.honor")
#     async def honor(self, raw_event: dict):
#         self_id = raw_event["self_id"]
#         account = self.connection.accounts.get(self_id)
#         if account is None:
#             logger.warning(f"Unknown account {self_id} sent message {raw_event}")
#             return
#
#         group = Selector().land(account.route["land"]).group(str(raw_event["group_id"]))
#         user = group.member(str(raw_event["user_id"]))
#         context = Context(account, group, user, group, group.member(str(self_id)))
#         return MetadataModified(
#             context,
#             user,
#             Honor,
#             {Honor.inh().name: ModifyDetail("set", raw_event["honor_type"])},
#         )
#
#     @m.entity(OneBot11Capability.event_callback, raw_event="notice.group_upload")
#     async def file_upload(self, raw_event: dict):
#         self_id = raw_event["self_id"]
#         account = self.connection.accounts.get(self_id)
#         if account is None:
#             logger.warning(f"Unknown account {self_id} sent message {raw_event}")
#             return
#
#         group = Selector().land(account.route["land"]).group(str(raw_event["group_id"]))
#         user = group.member(str(raw_event["user_id"]))
#         context = Context(account, group, user, group, group.member(str(self_id)))
#         return FileReceived(
#             context,
#             group.file(raw_event["file"]["id"]),
#         )

from __future__ import annotations

from datetime import datetime

from loguru import logger

from satori import EventType
from satori.model import Channel, ChannelType, Event, Guild, Login, Member, Role, User

from ..utils import GROUP_AVATAR_URL, USER_AVATAR_URL, OneBotNetwork
from .base import register_event


@register_event("notice.group_admin.set")
async def group_admin_set(login: Login, net: OneBotNetwork, raw: dict):
    guild = Guild(str(raw["group_id"]), avatar=GROUP_AVATAR_URL.format(group=raw["group_id"]))
    channel = Channel(str(raw["group_id"]), ChannelType.TEXT)
    user = User(str(raw["user_id"]), avatar=USER_AVATAR_URL.format(uin=raw["user_id"]))
    member = Member(user, avatar=USER_AVATAR_URL.format(uin=raw["user_id"]))
    role = Role("ADMINISTRATOR", "管理员")
    return Event(
        EventType.GUILD_MEMBER_UPDATED,
        datetime.now(),
        login=login,
        user=user,
        member=member,
        guild=guild,
        channel=channel,
        role=role,
    )


@register_event("notice.group_admin.unset")
async def group_admin_unset(login: Login, net: OneBotNetwork, raw: dict):
    guild = Guild(str(raw["group_id"]), avatar=GROUP_AVATAR_URL.format(group=raw["group_id"]))
    channel = Channel(str(raw["group_id"]), ChannelType.TEXT)
    user = User(str(raw["user_id"]), avatar=USER_AVATAR_URL.format(uin=raw["user_id"]))
    member = Member(user, avatar=USER_AVATAR_URL.format(uin=raw["user_id"]))
    role = Role("MEMBER", "成员")
    return Event(
        EventType.GUILD_MEMBER_UPDATED,
        datetime.now(),
        login=login,
        user=user,
        member=member,
        guild=guild,
        channel=channel,
        role=role,
    )


@register_event("notice.group_decrease.leave")
@register_event("notice.group_decrease.kick")
async def member_leave(login: Login, net: OneBotNetwork, raw: dict):
    if raw["user_id"] == 0:
        logger.warning(f"Received invalid user_id 0 in event {raw}")
        return
    guild = Guild(str(raw["group_id"]), avatar=GROUP_AVATAR_URL.format(group=raw["group_id"]))
    channel = Channel(str(raw["group_id"]), ChannelType.TEXT)
    user = User(str(raw["user_id"]), avatar=USER_AVATAR_URL.format(uin=raw["user_id"]))
    member = Member(user, avatar=USER_AVATAR_URL.format(uin=raw["user_id"]))
    operator = User(str(raw["operator_id"]), avatar=USER_AVATAR_URL.format(uin=raw["operator_id"]))
    return Event(
        EventType.GUILD_MEMBER_REMOVED,
        datetime.now(),
        login=login,
        user=user,
        member=member,
        guild=guild,
        channel=channel,
        operator=operator,
    )


@register_event("notice.group_decrease.kick_me")
async def member_kick_me(login: Login, net: OneBotNetwork, raw: dict):
    if raw["user_id"] == 0:
        logger.warning(f"Received invalid user_id 0 in event {raw}")
        return
    guild = Guild(str(raw["group_id"]), avatar=GROUP_AVATAR_URL.format(group=raw["group_id"]))
    channel = Channel(str(raw["group_id"]), ChannelType.TEXT)
    user = User(str(raw["user_id"]), avatar=USER_AVATAR_URL.format(uin=raw["user_id"]))
    member = Member(user, avatar=USER_AVATAR_URL.format(uin=raw["user_id"]))
    operator = User(str(raw["operator_id"]), avatar=USER_AVATAR_URL.format(uin=raw["operator_id"]))
    return Event(
        EventType.GUILD_REMOVED,
        datetime.now(),
        login=login,
        user=user,
        member=member,
        guild=guild,
        channel=channel,
        operator=operator,
    )


@register_event("notice.group_increase.approve")
@register_event("notice.group_increase.invite")
async def group_increase(login: Login, net: OneBotNetwork, raw: dict):
    guild = Guild(str(raw["group_id"]), avatar=GROUP_AVATAR_URL.format(group=raw["group_id"]))
    channel = Channel(str(raw["group_id"]), ChannelType.TEXT)
    if str(raw["user_id"]) == login.user.id:  # bot self joined new group
        return Event(
            EventType.GUILD_ADDED,
            datetime.now(),
            login=login,
            user=login.user,
            member=Member(login.user, avatar=USER_AVATAR_URL.format(uin=login.user.id)),
            guild=guild,
            channel=channel,
        )
    user = User(str(raw["user_id"]), avatar=USER_AVATAR_URL.format(uin=raw["user_id"]))
    member = Member(user, avatar=USER_AVATAR_URL.format(uin=raw["user_id"]))
    operator = User(str(raw["operator_id"]), avatar=USER_AVATAR_URL.format(uin=raw["operator_id"]))
    return Event(
        EventType.GUILD_MEMBER_ADDED,
        datetime.now(),
        login=login,
        user=user,
        member=member,
        guild=guild,
        channel=channel,
        operator=operator,
    )
