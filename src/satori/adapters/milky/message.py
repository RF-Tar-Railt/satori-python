from collections.abc import Iterator
from typing import Any

from satori.element import Text
from satori.parser import Element
from satori.model import MessageObject


class MilkyMessageEncoder:
    """Encodes Satori message elements to Milky protocol format."""

    def encode(self, elements: list[Element]) -> Any:
        """Encode message elements to milky format."""
        result = []
        for element in elements:
            if isinstance(element, Text):
                result.append({"type": "text", "data": {"text": element.text}})
            elif hasattr(element, 'type') and element.type == "at":
                result.append({"type": "at", "data": {"id": element.attrs.get("id", "")}})  
            elif hasattr(element, 'type') and element.type == "img":
                result.append({
                    "type": "image", 
                    "data": {
                        "url": element.attrs.get("src", ""),
                        "file": element.attrs.get("src", "")
                    }
                })
            elif hasattr(element, 'type') and element.type == "audio":
                result.append({
                    "type": "audio",
                    "data": {
                        "url": element.attrs.get("src", ""),
                        "file": element.attrs.get("src", "")
                    }
                })
            elif hasattr(element, 'type') and element.type == "video":
                result.append({
                    "type": "video", 
                    "data": {
                        "url": element.attrs.get("src", ""),
                        "file": element.attrs.get("src", "")
                    }
                })
            elif hasattr(element, 'type') and element.type == "file":
                result.append({
                    "type": "file",
                    "data": {
                        "url": element.attrs.get("src", ""),
                        "file": element.attrs.get("src", "")
                    }
                })
            else:
                # For other elements, encode based on milky protocol
                element_type = getattr(element, 'type', element.tag if hasattr(element, 'tag') else 'unknown')
                element_attrs = getattr(element, 'attrs', getattr(element, '_attrs', {}))
                result.append({"type": element_type, "data": element_attrs})
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
                elif segment_type == "at":
                    yield Element("at", attrs={"id": data.get("id", "")})
                elif segment_type == "image":
                    yield Element("img", attrs={"src": data.get("url", data.get("file", ""))})
                elif segment_type == "audio":
                    yield Element("audio", attrs={"src": data.get("url", data.get("file", ""))})
                elif segment_type == "video":
                    yield Element("video", attrs={"src": data.get("url", data.get("file", ""))})
                elif segment_type == "file":
                    yield Element("file", attrs={"src": data.get("url", data.get("file", ""))})
                else:
                    # Create element based on type
                    yield Element(segment_type, attrs=data)
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