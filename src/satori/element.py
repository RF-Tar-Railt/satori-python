from base64 import b64encode
from dataclasses import dataclass, fields
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional, Union
from typing_extensions import override

from .parser import RawElement, escape


@dataclass
class Element:
    @classmethod
    def from_raw(cls, raw: RawElement) -> "Element":
        _fields = {f.name for f in fields(cls)}
        attrs = {k: v for k, v in raw.attrs.items() if k in _fields}
        result = cls(**attrs)  # type: ignore
        for k, v in raw.attrs.items():
            if k not in _fields:
                setattr(result, k, v)
        return result

    def get_type(self) -> str:
        return self.__class__.__name__.lower()

    def __str__(self) -> str:
        def _attr(key: str, value: Any):
            if value is True:
                return key
            if value is False:
                return f"no-{key}"
            if isinstance(value, (int, float)):
                return f"{key}={value}"
            return f'{key}="{escape(str(value))}"'

        attrs = " ".join(_attr(k, v) for k, v in vars(self).items() if not k.startswith("_"))
        return f"<{self.get_type()} {attrs} />"


@dataclass
class Text(Element):
    text: str

    @override
    def __str__(self) -> str:
        return escape(self.text)


@dataclass
class At(Element):
    id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    type: Optional[str] = None

    @staticmethod
    def at_role(
        role: str,
        name: Optional[str] = None,
    ) -> "At":
        return At(role=role, name=name)

    @staticmethod
    def all(here: bool = False) -> "At":
        return At(type="here" if here else "all")


@dataclass
class Sharp(Element):
    id: str
    name: Optional[str] = None


@dataclass
class Link(Text):
    @override
    def __str__(self):
        return f'<a href="{escape(self.text)}"/>'


@dataclass
class Resource(Element):
    src: str
    cache: Optional[bool] = None
    timeout: Optional[str] = None

    @classmethod
    def of(
        cls,
        url: Optional[str] = None,
        path: Optional[Union[str, Path]] = None,
        raw: Optional[Union[bytes, BytesIO]] = None,
        mime: Optional[str] = None,
        cache: Optional[bool] = None,
        timeout: Optional[str] = None,
    ):
        if url:
            data = {"src": url}
        elif path:
            data = {"src": Path(path).as_uri()}
        elif raw and mime:
            bd = raw if isinstance(raw, bytes) else raw.getvalue()
            data = {"src": f"data:{mime};base64,{b64encode(bd).decode()}"}
        else:
            raise ValueError(f"{cls} need at least one of url, path and raw")
        if cache is not None:
            data["cache"] = cache
        if timeout is not None:
            data["timeout"] = timeout
        return cls(**data)


@dataclass
class Image(Resource):
    width: Optional[int] = None
    height: Optional[int] = None

    def get_type(self) -> str:
        return "img"


@dataclass
class Audio(Resource):
    pass


@dataclass
class Video(Resource):
    pass


@dataclass
class File(Resource):
    pass


@dataclass
class Bold(Text):
    @override
    def __str__(self):
        return f"<b>{escape(self.text)}</b>"


@dataclass
class Italic(Text):
    @override
    def __str__(self):
        return f"<i>{escape(self.text)}</i>"


@dataclass
class Underline(Text):
    @override
    def __str__(self):
        return f"<u>{escape(self.text)}</u>"


@dataclass
class Strikethrough(Text):
    @override
    def __str__(self):
        return f"<s>{escape(self.text)}</s>"


@dataclass
class Spoiler(Text):
    @override
    def __str__(self):
        return f"<spl>{escape(self.text)}</spl>"


@dataclass
class Code(Text):
    @override
    def __str__(self):
        return f"<code>{escape(self.text)}</code>"


@dataclass
class Superscript(Text):
    @override
    def __str__(self):
        return f"<sup>{escape(self.text)}</sup>"


@dataclass
class Subscript(Text):
    @override
    def __str__(self):
        return f"<sub>{escape(self.text)}</sub>"


@dataclass
class Br(Text):
    @override
    def __str__(self):
        return "<br/>"


@dataclass
class Paragraph(Text):
    @override
    def __str__(self):
        return f"<p>{escape(self.text)}</p>"


@dataclass
class Message(Element):
    id: Optional[str] = None
    forward: Optional[bool] = None
    content: Optional[List[Element]] = None

    @override
    def __str__(self):
        attr = []
        if self.id:
            attr.append(f'id="{escape(self.id)}"')
        if self.forward:
            attr.append("forward")
        _type = self.get_type()
        if not self.content:
            return f'<{_type} {" ".join(attr)} />'
        else:
            return f'<{_type} {" ".join(attr)}>{"".join(str(e) for e in self.content)}</{_type}>'


@dataclass
class Quote(Message):
    pass


@dataclass
class Author(Element):
    id: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None


ELEMENT_TYPE_MAP = {
    "text": Text,
    "at": At,
    "sharp": Sharp,
    "img": Image,
    "audio": Audio,
    "video": Video,
    "file": File,
    "author": Author,
}

STYLE_TYPE_MAP = {
    "b": Bold,
    "strong": Bold,
    "i": Italic,
    "em": Italic,
    "u": Underline,
    "ins": Underline,
    "s": Strikethrough,
    "del": Strikethrough,
    "spl": Spoiler,
    "code": Code,
    "sup": Superscript,
    "sub": Subscript,
    "p": Paragraph,
}


def transform(elements: List[RawElement]) -> List[Element]:
    msg = []
    for elem in elements:
        if elem.type in ELEMENT_TYPE_MAP:
            seg_cls = ELEMENT_TYPE_MAP[elem.type]
            msg.append(seg_cls.from_raw(elem))
        elif elem.type in ("a", "link"):
            msg.append(Link(elem.attrs["href"]))
        elif elem.type in STYLE_TYPE_MAP:
            seg_cls = STYLE_TYPE_MAP[elem.type]
            msg.append(seg_cls(elem.children[0].attrs["text"]))  # type: ignore
        elif elem.type in ("br", "newline"):
            msg.append(Br("\n"))
        elif elem.type == "message":
            res = Message.from_raw(elem)
            if elem.children:
                res.content = transform(elem.children)
            msg.append(res)
        elif elem.type == "quote":
            res = Quote.from_raw(elem)
            if elem.children:
                res.content = transform(elem.children)
            msg.append(res)
        else:
            msg.append(Text(str(elem)))
    return msg
