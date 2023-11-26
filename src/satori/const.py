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
    USER_CHANNEL_CREATE = "user.channel.create"

    GUILD_GET = "guild.get"
    GUILD_LIST = "guild.list"
    GUILD_APPROVE = "guild.approve"

    GUILD_MEMBER_LIST = "guild.member.list"
    GUILD_MEMBER_GET = "guild.member.get"
    GUILD_MEMBER_KICK = "guild.member.kick"
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
