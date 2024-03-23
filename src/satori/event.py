from satori.model import Channel, Event, Login, Member, MessageObject, Role, User, Guild, ButtonInteraction, ArgvInteraction


class MessageEvent(Event):
    channel: Channel
    member: Member
    message: MessageObject
    user: User

class UserEvent(Event):
    user: User

class GuildEvent(Event):
    guild: Guild

class GuildMemberEvent(GuildEvent):
    user: User
    member: Member

class GuildRoleEvent(GuildEvent):
    role: Role

class LoginEvent(Event):
    login: Login

class ReactionEvent(Event):
    channel: Channel
    user: User
    message: MessageObject

class ButtonInteractionEvent(Event):
    button: ButtonInteraction
    user: User
    channel: Channel

class CommandInteractionEvent(Event):
    message: MessageObject
    user: User
    channel: Channel

class ArgvInteractionEvent(Event):
    argv: ArgvInteraction
    user: User
    channel: Channel
