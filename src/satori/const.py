from enum import Enum


class Api(str, Enum):
    MESSAGE_CREATE = "message.create"
    MESSAGE_UPDATE = "message.update"
    MESSAGE_GET = "message.get"
    MESSAGE_DELETE = "message.delete"
    MESSAGE_LIST = "message.list"

    CHANNEL_GET = "channel.get"
    CHANNEL_LIST = "channel.list"
    CHANNEL_CREATE = "channel.create"
    CHANNEL_UPDATE = "channel.update"
    CHANNEL_DELETE = "channel.delete"
    CHANNEL_MUTE = "channel.mute"
    USER_CHANNEL_CREATE = "user.channel.create"

    GUILD_GET = "guild.get"
    GUILD_LIST = "guild.list"
    GUILD_APPROVE = "guild.approve"

    GUILD_MEMBER_LIST = "guild.member.list"
    GUILD_MEMBER_GET = "guild.member.get"
    GUILD_MEMBER_KICK = "guild.member.kick"
    GUILD_MEMBER_MUTE = "guild.member.mute"
    GUILD_MEMBER_APPROVE = "guild.member.approve"
    GUILD_MEMBER_ROLE_SET = "guild.member.role.set"
    GUILD_MEMBER_ROLE_UNSET = "guild.member.role.unset"

    GUILD_ROLE_LIST = "guild.role.list"
    GUILD_ROLE_CREATE = "guild.role.create"
    GUILD_ROLE_UPDATE = "guild.role.update"
    GUILD_ROLE_DELETE = "guild.role.delete"

    REACTION_CREATE = "reaction.create"
    REACTION_DELETE = "reaction.delete"
    REACTION_CLEAR = "reaction.clear"
    REACTION_LIST = "reaction.list"

    LOGIN_GET = "login.get"

    USER_GET = "user.get"
    FRIEND_LIST = "friend.list"
    FRIEND_APPROVE = "friend.approve"

    UPLOAD_CREATE = "upload.create"


class EventType(str, Enum):
    FRIEND_REQUEST = "friend-request"
    GUILD_ADDED = "guild-added"
    GUILD_MEMBER_ADDED = "guild-member-added"
    GUILD_MEMBER_REMOVED = "guild-member-removed"
    GUILD_MEMBER_REQUEST = "guild-member-request"
    GUILD_MEMBER_UPDATED = "guild-member-updated"
    GUILD_REMOVED = "guild-removed"
    GUILD_REQUEST = "guild-request"
    GUILD_ROLE_CREATED = "guild-role-created"
    GUILD_ROLE_DELETED = "guild-role-deleted"
    GUILD_ROLE_UPDATED = "guild-role-updated"
    GUILD_UPDATED = "guild-updated"
    LOGIN_ADDED = "login-added"
    LOGIN_REMOVED = "login-removed"
    LOGIN_UPDATED = "login-updated"
    MESSAGE_CREATED = "message-created"
    MESSAGE_DELETED = "message-deleted"
    MESSAGE_UPDATED = "message-updated"
    REACTION_ADDED = "reaction-added"
    REACTION_REMOVED = "reaction-removed"
    INTERNAL = "internal"
    INTERACTION_BUTTON = "interaction/button"
    INTERACTION_COMMAND = "interaction/command"
