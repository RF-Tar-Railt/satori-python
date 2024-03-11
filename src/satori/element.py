from base64 import b64encode
from dataclasses import InitVar, dataclass, field, fields
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union
from typing_extensions import override

from .parser import Element as RawElement
from .parser import escape, param_case

TE = TypeVar("TE", bound="Element")


@dataclass
class Element:
    _attrs: Dict[str, Any] = field(init=False, default_factory=dict, repr=False)
    _children: List["Element"] = field(init=False, default_factory=list)

    @property
    def tag(self) -> str:
        return self.__class__.__name__.lower()

    def __post_init__(self):
        for f in fields(self):
            if f.name in ("_attrs", "_children"):
                continue
            self._attrs[f.name] = getattr(self, f.name)
        self._attrs = {k: v for k, v in self._attrs.items() if v is not None}

    def attributes(self) -> str:
        def _attr(key: str, value: Any):
            if value is None:
                return ""
            key = param_case(key)
            if value is True:
                return f" {key}"
            if value is False:
                return f" no-{key}"
            return f' {key}="{escape(str(value), True)}"'

        return "".join(_attr(k, v) for k, v in self._attrs.items())

    def dumps(self, strip: bool = False) -> str:
        if self.tag == "text" and "text" in self._attrs:
            return self._attrs["text"] if strip else escape(self._attrs["text"])
        inner = "".join(c.dumps(strip) for c in self._children)
        if strip:
            return inner
        attrs = self.attributes()
        if not self._children:
            return f"<{self.tag}{attrs}/>"
        return f"<{self.tag}{attrs}>{inner}</{self.tag}>"

    def __str__(self) -> str:
        return self.dumps()

    def __call__(self, *content: Union[str, "Element"]):
        self._children.extend(Text(i) if isinstance(i, str) else i for i in content)
        self.__post_call__()
        return self

    def __post_call__(self):
        ...


@dataclass
class Text(Element):
    """一段纯文本。"""

    text: str

    @override
    def dumps(self, strip: bool = False) -> str:
        return self.text if strip else escape(self.text)


@dataclass
class At(Element):
    """<at> 元素用于提及某个或某些用户。"""

    id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    type: Optional[str] = None

    @staticmethod
    def role_(
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

    def __post_call__(self):
        if not self._children:
            return
        if len(self._children) == 1 and isinstance(self._children[0], Text):
            return
        raise ValueError("Link can only have one Text child")

    @property
    @override
    def tag(self) -> str:
        return "a"

    @override
    def attributes(self) -> str:
        return f' href="{escape(self.url)}"'


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
        super().__post_init__()
        if extra:
            self._attrs.update(extra)


@dataclass
class Image(Resource):
    """<img> 元素用于表示图片。"""

    width: Optional[int] = None
    height: Optional[int] = None

    @property
    @override
    def tag(self) -> str:
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


@dataclass(init=False)
class Style(Element):
    """样式元素的基类。"""

    def __init__(self, *text: Union[str, Text, "Style"]):
        super().__init__()
        self.__call__(*text)


class Bold(Style):
    """<b> 或 <strong> 元素用于将其中的内容以粗体显示。"""

    @property
    @override
    def tag(self) -> str:
        return "b"


class Italic(Style):
    """<i> 或 <em> 元素用于将其中的内容以斜体显示。"""

    @property
    @override
    def tag(self) -> str:
        return "i"


class Underline(Style):
    """<u> 或 <ins> 元素用于为其中的内容附加下划线。"""

    @property
    @override
    def tag(self) -> str:
        return "u"


class Strikethrough(Style):
    """<s> 或 <del> 元素用于为其中的内容附加删除线。"""

    @property
    @override
    def tag(self) -> str:
        return "s"


class Spoiler(Style):
    """<spl> 元素用于将其中的内容标记为剧透 (默认会被隐藏，点击后才显示)。"""

    @property
    @override
    def tag(self) -> str:
        return "spl"


class Code(Style):
    """<code> 元素用于将其中的内容以等宽字体显示 (通常还会有特定的背景色)。"""

    @property
    @override
    def tag(self) -> str:
        return "code"


class Superscript(Style):
    """<sup> 元素用于将其中的内容以上标显示。"""

    @property
    @override
    def tag(self) -> str:
        return "sup"


class Subscript(Style):
    """<sub> 元素用于将其中的内容以下标显示。"""

    @property
    @override
    def tag(self) -> str:
        return "sub"


class Br(Style):
    """<br> 元素表示一个独立的换行。"""

    @override
    def __post_call__(self):
        if self._children:
            raise ValueError("Br cannot have children")

    @property
    @override
    def tag(self) -> str:
        return "br"


class Paragraph(Style):
    """<p> 元素表示一个段落。在渲染时，它与相邻的元素之间会确保有一个换行。"""

    @property
    @override
    def tag(self) -> str:
        return "p"


@dataclass(init=False)
class Message(Element):
    """<message> 元素的基本用法是表示一条消息。

    子元素对应于消息的内容。如果其没有子元素，则消息不会被发送。
    """

    id: Optional[str]
    forward: Optional[bool]

    def __init__(
        self,
        id: Optional[str] = None,
        forward: Optional[bool] = None,
        content: Optional[List[Union[str, Element]]] = None,
    ):
        self.id = id
        self.forward = forward
        super().__init__()
        self.__call__(*content or [])


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
    id: Optional[str] = None
    href: Optional[str] = None
    text: Optional[str] = None
    theme: Optional[str] = None

    @classmethod
    def action(cls, button_id: str, theme: Optional[str] = None):
        return Button("action", id=button_id, theme=theme)

    @classmethod
    def link(cls, url: str, theme: Optional[str] = None):
        return Button("link", href=url, theme=theme)

    @classmethod
    def input(cls, text: str, theme: Optional[str] = None):
        return Button("input", text=text, theme=theme)

    def attributes(self) -> str:
        attr = [f' type="{escape(self.type)}"']
        if self.type == "action":
            attr.append(escape(f' id="{self.id}"'))
        if self.type == "link":
            attr.append(escape(f' href="{self.href}"'))
        if self.type == "input":
            attr.append(escape(f' text="{self.text}"'))
        if self.theme:
            attr.append(escape(f' theme="{self.theme}"'))
        return "".join(attr)

    @override
    def __post_call__(self):
        if not self._children:
            return
        if len(self._children) == 1 and isinstance(self._children[0], Text):
            return
        raise ValueError("Button can only have one Text child")


@dataclass(init=False)
class Custom(Element):
    """自定义元素用于构造标准元素以外的元素"""

    type: str

    def __init__(
        self,
        type: str,
        attrs: Optional[Dict[str, Any]] = None,
        children: Optional[List[Union[str, Element]]] = None,
    ):
        self.type = type
        super().__init__()
        if not hasattr(self, "_attrs"):
            self._attrs = attrs or {}
        else:
            self._attrs.update(attrs or {})
        if not hasattr(self, "_children"):
            self._children = [Text(i) if isinstance(i, str) else i for i in (children or [])]
        else:
            self._children.extend(Text(i) if isinstance(i, str) else i for i in (children or []))

    @property
    @override
    def tag(self) -> str:
        return self.type


@dataclass
class Raw(Element):
    """Raw 元素表示原始文本"""

    content: str

    @override
    def dumps(self, strip: bool = False):
        return self.content if strip else escape(self.content)


ELEMENT_TYPE_MAP = {
    "text": Text,
    "at": At,
    "sharp": Sharp,
    "img": Image,
    "image": Image,
    "audio": Audio,
    "video": Video,
    "file": File,
    "author": Author,
}

STYLE_TYPE_MAP = {
    "b": Bold,
    "strong": Bold,
    "bold": Bold,
    "i": Italic,
    "em": Italic,
    "italic": Italic,
    "u": Underline,
    "ins": Underline,
    "underline": Underline,
    "s": Strikethrough,
    "del": Strikethrough,
    "strike": Strikethrough,
    "strikethrough": Strikethrough,
    "spl": Spoiler,
    "spoiler": Spoiler,
    "code": Code,
    "sup": Superscript,
    "superscript": Superscript,
    "sub": Subscript,
    "subscript": Subscript,
    "p": Paragraph,
    "paragraph": Paragraph,
    "br": Br,
}


def transform(elements: List[RawElement]) -> List[Element]:
    msg = []
    for elem in elements:
        tag = elem.tag()
        if tag in ELEMENT_TYPE_MAP:
            seg_cls = ELEMENT_TYPE_MAP[tag]
            msg.append(seg_cls(**elem.attrs))
        elif tag in ("a", "link"):
            link = Link(elem.attrs["href"])
            if elem.children:
                link(*transform(elem.children))
            msg.append(link)
        elif tag == "button":
            button = Button(**elem.attrs)
            if elem.children:
                button(*transform(elem.children))
        elif tag in STYLE_TYPE_MAP:
            seg_cls = STYLE_TYPE_MAP[tag]
            msg.append(seg_cls()(*transform(elem.children)))
        elif tag in ("br", "newline"):
            msg.append(Br())
        elif tag == "message":
            msg.append(Message(**elem.attrs)(*transform(elem.children)))
        elif tag == "quote":
            msg.append(Quote(**elem.attrs)(*transform(elem.children)))
        else:
            msg.append(Custom(elem.type, elem.attrs)(*transform(elem.children)))
    return msg


class E:
    text = Text
    at = At
    at_role = At.role_
    at_all = At.all
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
