from satori.model import (
    ArgvInteraction,
    ButtonInteraction,
    Channel,
    EmojiObject,
    Event,
    Guild,
    LoginPartial,
    Member,
    MessageObject,
    Role,
    User,
)


class MessageEvent(Event):
    channel: Channel
    member: Member
    message: MessageObject
    user: User


class UserEvent(Event):
    user: User


class GuildEvent(Event):
    guild: Guild


class ChannelEvent(GuildEvent):
    channel: Channel


class GuildMemberEvent(GuildEvent):
    user: User
    member: Member


class GuildRoleEvent(GuildEvent):
    role: Role


class GuildEmojiEvent(GuildEvent):
    emoji: EmojiObject


class LoginEvent(Event):
    login: LoginPartial


class ReactionEvent(Event):
    channel: Channel
    user: User
    message: MessageObject
    emoji: EmojiObject


class ButtonInteractionEvent(Event):
    button: ButtonInteraction
    user: User
    channel: Channel


class ArgvInteractionEvent(Event):
    argv: ArgvInteraction
    user: User
    channel: Channel


class InternalEvent(Event):
    _type: str
    _data: dict
