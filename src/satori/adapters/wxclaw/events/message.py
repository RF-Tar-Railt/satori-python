from datetime import datetime

from satori import EventType
from satori.model import Channel, ChannelType, Event, Login, MessageObject, User

from ..message import decode_elements
from ..models import WeixinMessage
from ..network import WxClawNetwork
from .base import register_event


@register_event("message.text")
@register_event("message.image")
@register_event("message.voice")
@register_event("message.file")
@register_event("message.video")
async def message_created(login: Login, network: WxClawNetwork, msg: WeixinMessage) -> Event | None:
    user_id = msg.from_user_id
    if not user_id:
        return None

    network.update_context(user_id, msg.context_token or "", msg.session_id or "")
    channel = Channel(f"private:{user_id}", ChannelType.DIRECT)
    user = User(user_id, user_id)

    created_ms = msg.create_time_ms
    if created_ms is None:
        created_ms = next(
            (item.create_time_ms for item in msg.item_list or [] if item.create_time_ms is not None),
            None,
        )
    updated_ms = msg.update_time_ms
    if updated_ms is None:
        updated_ms = next(
            (item.update_time_ms for item in msg.item_list or [] if item.update_time_ms is not None),
            None,
        )
    created_at = datetime.fromtimestamp(created_ms / 1000) if created_ms is not None else datetime.now()
    updated_at = datetime.fromtimestamp(updated_ms / 1000) if updated_ms is not None else None
    message_id = next(
        (
            str(value)
            for value in (
                msg.message_id,
                msg.client_id,
                next((item.msg_id for item in msg.item_list or [] if item.msg_id), None),
                msg.seq,
            )
            if value is not None
        ),
        f"{user_id}:{int(created_at.timestamp() * 1000)}",
    )
    message = MessageObject.from_elements(
        message_id,
        decode_elements(network, msg.item_list or []),
        channel=channel,
        user=user,
        created_at=created_at,
        updated_at=updated_at,
    )
    referrer = {
        key: value
        for key, value in {
            "session_id": msg.session_id,
            "context_token": msg.context_token,
        }.items()
        if value
    }
    return Event(
        EventType.MESSAGE_CREATED,
        created_at,
        login,
        channel=channel,
        user=user,
        message=message,
        referrer=referrer,
    )
