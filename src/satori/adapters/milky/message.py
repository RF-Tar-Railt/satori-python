from collections.abc import Iterator
from typing import Any

from satori.element import Element, Text
from satori.model import MessageObject


class MilkyMessageEncoder:
    """Encodes Satori message elements to Milky protocol format."""

    def encode(self, elements: list[Element]) -> Any:
        """Encode message elements to milky format."""
        result = []
        for element in elements:
            if isinstance(element, Text):
                result.append({"type": "text", "data": {"text": element.attrs.get("text", "")}})
            else:
                # For other elements, encode based on milky protocol
                result.append({"type": element.tag, "data": element.attrs})
        return result


def decode(message: Any) -> Iterator[Element]:
    """Decode milky message format to Satori elements."""
    if isinstance(message, str):
        yield Text(message)
    elif isinstance(message, list):
        for segment in message:
            if isinstance(segment, dict):
                segment_type = segment.get("type", "text")
                data = segment.get("data", {})
                
                if segment_type == "text":
                    yield Text(data.get("text", ""))
                else:
                    # Create element based on type
                    yield Element(segment_type, data)
    else:
        yield Text(str(message))


def parse_message_object(data: dict) -> MessageObject:
    """Parse milky message data to MessageObject."""
    elements = list(decode(data.get("message", [])))
    return MessageObject(
        id=str(data.get("message_id", "")),
        content=elements,
        created_at=data.get("time"),
    )