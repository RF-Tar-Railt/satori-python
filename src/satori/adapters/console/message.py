import re

from nonechat.message import ConsoleMessage, Markdown
from nonechat.message import Text as ConsoleText

from satori.element import At, Text, transform
from satori.parser import parse


def encode_message(message: ConsoleMessage) -> str:
    content = str(message)
    content = re.sub(r"@(\w+)", r"@<at id='\1'>", content)  # Handle mentions
    return content


def decode_message(content: str) -> ConsoleMessage:
    elements = []
    msg = transform(parse(content))
    for seg in msg:
        if isinstance(seg, Text):
            elements.append(ConsoleText(seg.text))
        elif isinstance(seg, At):
            elements.append(ConsoleText(f"@{seg.id}"))
        else:
            elements.append(Markdown(str(seg)))
    return ConsoleMessage(elements)
