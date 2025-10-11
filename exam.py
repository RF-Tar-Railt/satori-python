from satori import At, Link, Sharp, Text, transform
from satori.parser import parse

print(transform(parse('<at id="12345" name="abcd-def"/> foobar')))

a = Text("1234<foo>")
role = At.role_("admin")
chl = Sharp("abcd")
link = Link("www.baidu.com")
link1 = Link("github.com/RF-Tar-Railt/satori-python")("satori-python")
print(a)
print(role)
print(chl)
print(link)
print(link1)

from satori import Image, Video

image = Image.of(url="https://example.com/image.png", name="image.png")
print(image)
image1 = Image.of(raw=b"\x89PNG\r\n\x1a\n...", name="image.png")
print(image1)
print(
    repr(Video.unpack(
        {
            "src": "https://example.com/video.mp4",
            "title": "video.mp4",
            "width": "123",
            "height": "456",
            "poster": "https://example.com/poster.png",
        }
    ))
)

from satori import Bold, Italic, Paragraph, Underline

text = Bold("hello", Italic("world,"), Underline()("Satori!"), Paragraph("This is a paragraph."))
print(text)

from satori import Author, Message

message = Message(forward=True)(
    Message(id="123456789"),
    Message(id="987654321"),
    Message(content=[Author(id="123456789"), "Hello, "]),
    Message()(Author(id="123456789"), "World!"),
)
print(message)

from satori import E

print(E("<qq:passive id={ id }/>", {"id": "123456789"}))

from satori import register_element
from satori.element import Element
from dataclasses import dataclass


@dataclass(repr=False)
class QQPassive(Element):
    id: str

    @property
    def tag(self) -> str:
        return "qq:passive"


register_element(QQPassive, "qq:passive")

print(QQPassive(id="123456789"))
print(transform(parse("<qq:passive id='123456789'/>")))
