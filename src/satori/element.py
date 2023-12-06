from base64 import b64encode
from dataclasses import InitVar, dataclass, fields
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from typing_extensions import override

from .parser import RawElement, escape

TE = TypeVar("TE", bound="Element")


@dataclass
class Element:
    @classmethod
    def from_raw(cls: Type[TE], raw: RawElement) -> TE:
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
        attrs = f" {attrs}" if attrs else ""
        return f"<{self.get_type()}{attrs}/>"


@dataclass
class Text(Element):
    """一段纯文本。"""

    text: str

    @override
    def __str__(self) -> str:
        return escape(self.text)


@dataclass
class At(Element):
    """<at> 元素用于提及某个或某些用户。"""

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
    """<sharp> 元素用于提及某个频道。"""

    id: str
    name: Optional[str] = None


@dataclass
class Link(Element):
    """<a> 元素用于显示一个链接。"""

    url: str
    display: Optional[str] = None

    @classmethod
    @override
    def from_raw(cls, raw: RawElement) -> "Link":
        res = cls(raw.attrs["href"], raw.children[0].attrs["text"] if raw.children else None)
        for k, v in raw.attrs.items():
            if k != "href":
                setattr(res, k, v)
        return res

    @override
    def __str__(self):
        if not self.display:
            return f'<a href="{escape(self.url)}"/>'
        return f'<a href="{escape(self.url)}">{escape(self.display)}</a>'


@dataclass
class Resource(Element):
    src: str
    extra: InitVar[Optional[Dict[str, Any]]] = None
    cache: Optional[bool] = None
    timeout: Optional[str] = None

    @classmethod
    def of(
        cls,
        url: Optional[str] = None,
        path: Optional[Union[str, Path]] = None,
        raw: Optional[Union[bytes, BytesIO]] = None,
        mime: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        cache: Optional[bool] = None,
        timeout: Optional[str] = None,
    ):
        data: Dict[str, Any] = {"extra": extra}
        if url is not None:
            data = {"src": url}
        elif path:
            data = {"src": Path(path).as_uri()}
        elif raw and mime:
            bd = raw.getvalue() if isinstance(raw, BytesIO) else raw
            data = {"src": f"data:{mime};base64,{b64encode(bd).decode()}"}
        else:
            raise ValueError(f"{cls} need at least one of url, path and raw")
        if cache is not None:
            data["cache"] = cache
        if timeout is not None:
            data["timeout"] = timeout
        return cls(**data)

    def __post_init__(self, extra: Optional[Dict[str, Any]] = None):
        if extra:
            for k, v in extra.items():
                setattr(self, k, True if v is ... else v)


@dataclass
class Image(Resource):
    """<img> 元素用于表示图片。"""

    width: Optional[int] = None
    height: Optional[int] = None

    def get_type(self) -> str:
        return "img"


@dataclass
class Audio(Resource):
    """<audio> 元素用于表示语音。"""

    pass


@dataclass
class Video(Resource):
    """<video> 元素用于表示视频。"""

    pass


@dataclass
class File(Resource):
    """<file> 元素用于表示文件。"""

    pass


@dataclass
class Style(Text):
    @classmethod
    @override
    def from_raw(cls, raw: RawElement):
        res = cls(raw.children[0].attrs["text"])
        for k, v in raw.attrs.items():
            setattr(res, k, v)
        return res


@dataclass
class Bold(Style):
    """<b> 或 <strong> 元素用于将其中的内容以粗体显示。"""

    @override
    def __str__(self):
        return f"<b>{escape(self.text)}</b>"


@dataclass
class Italic(Style):
    """<i> 或 <em> 元素用于将其中的内容以斜体显示。"""

    @override
    def __str__(self):
        return f"<i>{escape(self.text)}</i>"


@dataclass
class Underline(Style):
    """<u> 或 <ins> 元素用于为其中的内容附加下划线。"""

    @override
    def __str__(self):
        return f"<u>{escape(self.text)}</u>"


@dataclass
class Strikethrough(Style):
    """<s> 或 <del> 元素用于为其中的内容附加删除线。"""

    @override
    def __str__(self):
        return f"<s>{escape(self.text)}</s>"


@dataclass
class Spoiler(Style):
    """<spl> 元素用于将其中的内容标记为剧透 (默认会被隐藏，点击后才显示)。"""

    @override
    def __str__(self):
        return f"<spl>{escape(self.text)}</spl>"


@dataclass
class Code(Style):
    """<code> 元素用于将其中的内容以等宽字体显示 (通常还会有特定的背景色)。"""

    @override
    def __str__(self):
        return f"<code>{escape(self.text)}</code>"


@dataclass
class Superscript(Style):
    """<sup> 元素用于将其中的内容以上标显示。"""

    @override
    def __str__(self):
        return f"<sup>{escape(self.text)}</sup>"


@dataclass
class Subscript(Style):
    """<sub> 元素用于将其中的内容以下标显示。"""

    @override
    def __str__(self):
        return f"<sub>{escape(self.text)}</sub>"


@dataclass
class Br(Style):
    """<br> 元素表示一个独立的换行。"""

    @override
    def __str__(self):
        return "<br/>"


@dataclass
class Paragraph(Style):
    """<p> 元素表示一个段落。在渲染时，它与相邻的元素之间会确保有一个换行。"""

    @override
    def __str__(self):
        return f"<p>{escape(self.text)}</p>"


@dataclass
class Message(Element):
    """<message> 元素的基本用法是表示一条消息。

    子元素对应于消息的内容。如果其没有子元素，则消息不会被发送。
    """

    id: Optional[str]
    forward: Optional[bool]
    content: List[Element]

    def __init__(
        self,
        id: Optional[str] = None,
        forward: Optional[bool] = None,
        content: Optional[List[Union[str, Element]]] = None,
    ):
        self.id = id
        self.forward = forward
        self.content = [Text(i) if isinstance(i, str) else i for i in content or []]

    def __call__(self, *content: Union[str, Element]):
        self.content.extend(Text(i) if isinstance(i, str) else i for i in content)
        return self

    @override
    def __str__(self):
        attr = []
        if self.id:
            attr.append(f'id="{escape(self.id)}"')
        if self.forward:
            attr.append("forward")
        _type = self.get_type()
        attrs = (" " + " ".join(attr)) if attr else ""
        if not self.content:
            return f"<{_type}{attrs}/>"
        else:
            return f'<{_type}{attrs}>{"".join(str(e) for e in self.content)}</{_type}>'


@dataclass
class Quote(Message):
    """<quote> 元素用于表示对消息引用。

    它的子元素会被渲染为引用的内容。
    """

    pass


@dataclass
class Author(Element):
    """<author> 元素用于表示消息的作者。它的子元素会被渲染为作者的名字。"""

    id: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None


@dataclass
class Button(Element):
    """<button> 元素用于表示一个按钮。它的子元素会被渲染为按钮的文本。"""

    type: str
    display: Optional[str] = None
    id: Optional[str] = None
    href: Optional[str] = None
    text: Optional[str] = None
    theme: Optional[str] = None

    @classmethod
    def action(cls, button_id: str, display: Optional[str] = None, theme: Optional[str] = None):
        return Button("action", id=button_id, display=display, theme=theme)

    @classmethod
    def link(cls, url: str, display: Optional[str] = None, theme: Optional[str] = None):
        return Button("link", href=url, display=display, theme=theme)

    @classmethod
    def input(cls, text: str, display: Optional[str] = None, theme: Optional[str] = None):
        return Button("input", text=text, display=display, theme=theme)

    @classmethod
    @override
    def from_raw(cls, raw: RawElement) -> "Button":
        res = cls(**raw.attrs)
        res.display = raw.children[0].attrs["text"] if raw.children else None
        return res

    @override
    def __str__(self):
        attr = [f'type="{escape(self.type)}"']
        if self.type == "action":
            attr.append(escape(f'id="{self.id}"'))
        if self.type == "link":
            attr.append(escape(f'href="{self.href}"'))
        if self.type == "input":
            attr.append(escape(f'text="{self.text}"'))
        if self.theme:
            attr.append(escape(f'theme="{self.theme}"'))
        if self.display:
            return f'<button {" ".join(attr)}>{escape(self.display)}</button>'
        return f'<button {" ".join(attr)} />'


@dataclass
class Custom(Element):
    """自定义元素用于构造标准元素以外的元素"""

    type: str
    attrs: Dict[str, Any]
    children: List[Element]

    def __init__(
        self,
        type: str,
        attrs: Optional[Dict[str, Any]] = None,
        children: Optional[List[Union[str, Element]]] = None,
    ):
        self.type = type
        self.attrs = attrs or {}
        self.children = [Text(i) if isinstance(i, str) else i for i in children or []]

    def __call__(self, *children: Union[str, Element]):
        self.children.extend(Text(i) if isinstance(i, str) else i for i in children)
        return self

    @override
    def get_type(self) -> str:
        return self.type

    @override
    def __str__(self) -> str:
        def _attr(key: str, value: Any):
            if value is True:
                return key
            if value is False:
                return f"no-{key}"
            if isinstance(value, (int, float)):
                return f"{key}={value}"
            return f'{key}="{escape(str(value))}"'

        attrs = " ".join(_attr(k, v) for k, v in self.attrs.items() if not k.startswith("_"))
        attrs = f" {attrs}" if attrs else ""
        if self.children:
            return f"<{self.get_type()}{attrs}>{''.join(str(e) for e in self.children)}</{self.get_type()}>"
        return f"<{self.get_type()}{attrs}/>"


@dataclass
class Raw(Element):
    """Raw 元素表示原始文本"""

    content: str

    @override
    def __str__(self):
        return self.content


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
            msg.append(Link.from_raw(elem))
        elif elem.type == "button":
            msg.append(Button.from_raw(elem))
        elif elem.type in STYLE_TYPE_MAP:
            seg_cls = STYLE_TYPE_MAP[elem.type]
            msg.append(seg_cls.from_raw(elem))
        elif elem.type in ("br", "newline"):
            msg.append(Br("\n"))
        elif elem.type == "message":
            msg.append(Message.from_raw(elem)(*transform(elem.children)))
        elif elem.type == "quote":
            msg.append(Quote.from_raw(elem)(*transform(elem.children)))
        else:
            msg.append(Custom(elem.type, elem.attrs)(*transform(elem.children)))
    return msg


class E:
    text = Text
    at = At
    at_role = At.at_role
    all = At.all
    sharp = Sharp
    link = Link
    image = Image.of
    audio = Audio.of
    video = Video.of
    file = File.of
    resource = Resource
    bold = Bold
    italic = Italic
    underline = Underline
    strikethrough = Strikethrough
    spoiler = Spoiler
    code = Code
    sup = Superscript
    sub = Subscript
    br = Br
    paragraph = Paragraph
    message = Message
    quote = Quote
    author = Author
    custom = Custom
    raw = Raw
    button = Button
    action_button = Button.action
    link_button = Button.link
    input_button = Button.input

    def __new__(cls, *args, **kwargs):
        raise TypeError("E is not instantiable")
