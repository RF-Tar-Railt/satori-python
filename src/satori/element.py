from base64 import b64encode
from collections.abc import Callable, Sequence
from dataclasses import InitVar, dataclass, field
from io import BytesIO
from pathlib import Path
from types import UnionType
from typing import Any, ClassVar, Final, TypeVar, Union, final, get_args, get_origin, overload
from typing_extensions import override

from .parser import Element as RawElement
from .parser import escape, param_case, parse
from .parser import select as select_raw
from .utils import decode

TE = TypeVar("TE", bound="Element")


def conv_bool(v: str) -> bool:
    if v.lower() not in ("true", "false"):
        raise ValueError(v)
    return v.lower() == "true"


@dataclass(repr=False)
class Element:
    _attrs: dict[str, Any] = field(init=False, default_factory=dict)
    _children: list["Element"] = field(init=False, default_factory=list)

    __names__: ClassVar[tuple[str, ...]]
    __convert_fields__: ClassVar[dict[str, Callable[[str], Any]]]

    def __init_subclass__(cls, **kwargs):
        cls.__convert_fields__ = {}
        annotations = cls.__annotations__
        for name, typ in annotations.items():
            if name.startswith("_"):
                continue
            # _type = get_args(typ)[0] if hasattr(typ, "__origin__") else typ
            orig = get_origin(typ)
            if orig in (Union, UnionType):
                args = get_args(typ)
                if len(args) == 2 and type(None) in args:
                    _type = args[0] if args[1] is type(None) else args[1]
                else:
                    _type = args[0]
            else:
                _type = typ
            if _type is not str:
                if _type is bool:
                    cls.__convert_fields__[name] = conv_bool
                elif _type in (list, dict):
                    cls.__convert_fields__[name] = decode
                else:
                    cls.__convert_fields__[name] = _type

    @property
    def children(self) -> list["Element"]:
        return self._children

    @property
    def tag(self) -> str:
        return self.__class__.__name__.lower()

    @classmethod
    def unpack(cls, attrs: dict[str, Any]):
        data = {}
        names = getattr(cls, "__names__", None)
        for name in cls.__dataclass_fields__.keys():
            if name not in attrs:
                continue
            if name in cls.__convert_fields__:
                data[name] = cls.__convert_fields__[name](attrs[name])
            else:
                data[name] = attrs[name]
        obj = cls(**{k: v for k, v in data.items() if names is None or k in names})  # type: ignore
        obj._attrs.update(data)
        return obj

    def __post_init__(self):
        self._attrs = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

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

    def __repr__(self) -> str:
        args = {**self._attrs}
        elem = f"{self.__class__.__name__}(" + ", ".join(f"{k}={v!r}" for k, v in args.items())
        if self._children:
            elem += ", { " + ", ".join(repr(i) for i in self._children) + " }"
        return elem + ")"

    def __call__(self, *content: "str | Element"):
        self._children.extend(Text(i) if isinstance(i, str) else i for i in content)
        self.__post_call__()
        return self

    def __post_call__(self): ...

    def __getitem__(self, key: str) -> Any:
        return self._attrs[key]


@dataclass(repr=False)
class Text(Element):
    """一段纯文本。"""

    text: str

    @override
    def dumps(self, strip: bool = False) -> str:
        return self.text if strip else escape(self.text)


@dataclass(repr=False)
class At(Element):
    """<at> 元素用于提及某个或某些用户。"""

    id: str | None = None
    name: str | None = None
    role: str | None = None
    type: str | None = None

    @staticmethod
    def role_(
        role: str,
        name: str | None = None,
    ) -> "At":
        return At(role=role, name=name)

    @staticmethod
    def all(here: bool = False) -> "At":
        return At(type="here" if here else "all")


@dataclass(repr=False)
class Sharp(Element):
    """<sharp> 元素用于提及某个频道。"""

    id: str
    name: str | None = None


@dataclass(repr=False)
class Link(Element):
    """<a> 元素用于显示一个链接。"""

    href: str

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

    @property
    def url(self) -> str:
        return self.href


@dataclass(repr=False)
class Resource(Element):
    src: str
    title: str | None = None
    extra: InitVar[dict[str, Any] | None] = None
    cache: bool | None = None
    timeout: int | None = None

    __names__ = ("src", "title")

    @classmethod
    def of(
        cls,
        url: str | None = None,
        path: str | Path | None = None,
        raw: bytes | BytesIO | None = None,
        mime: str | None = None,
        name: str | None = None,
        duration: float | None = None,
        poster: str | None = None,
        extra: dict[str, Any] | None = None,
        cache: bool | None = None,
        timeout: int | None = None,
        **kwargs,
    ):
        data: dict[str, Any] = {"extra": extra or kwargs}
        if url is not None:
            data |= {"src": url}
        elif path:
            data |= {"src": Path(path).as_uri()}
        elif raw and mime:
            bd = raw.getvalue() if isinstance(raw, BytesIO) else raw
            data |= {"src": f"data:{mime};base64,{b64encode(bd).decode('utf-8')}"}
        else:
            raise ValueError(f"{cls} need at least one of url, path and raw")
        if name is not None:
            data["title"] = name
        if duration is not None and cls is Audio:
            data["duration"] = duration
        if poster is not None and cls in (Video, Audio, File):
            data["poster"] = poster
        if cache is not None:
            data["cache"] = cache
        if timeout is not None:
            data["timeout"] = timeout
        return cls(**data)

    def __post_init__(self, extra: dict[str, Any] | None = None):
        super().__post_init__()
        if extra:
            self._attrs.update(extra)


@dataclass(repr=False)
class Image(Resource):
    """<img> 元素用于表示图片。"""

    width: int | None = None
    height: int | None = None

    __names__ = ("src", "title", "width", "height")

    @property
    @override
    def tag(self) -> str:
        return "img"


@dataclass(repr=False)
class Audio(Resource):
    """<audio> 元素用于表示语音。"""

    duration: float | None = None
    poster: str | None = None

    __names__ = ("src", "title", "duration", "poster")


@dataclass(repr=False)
class Video(Resource):
    """<video> 元素用于表示视频。"""

    width: int | None = None
    height: int | None = None
    duration: float | None = None
    poster: str | None = None

    __names__ = ("src", "title", "width", "height", "duration", "poster")


@dataclass(repr=False)
class File(Resource):
    """<file> 元素用于表示文件。"""

    poster: str | None = None

    __names__ = ("src", "title", "poster")


@dataclass(init=False, repr=False)
class Style(Element):
    """样式元素的基类。"""

    __names__ = ()

    def __init__(self, *text: "str | Text | Style"):
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


@dataclass(init=False, repr=False)
class Message(Element):
    """<message> 元素的基本用法是表示一条消息。

    子元素对应于消息的内容。如果其没有子元素，则消息不会被发送。
    """

    id: str | None
    forward: bool | None

    def __init__(
        self,
        id: str | None = None,
        forward: bool | None = None,
        content: list[str | Element] | None = None,
    ):
        self.id = id
        self.forward = forward
        super().__init__()
        self.__call__(*content or [])


class Quote(Message):
    """<quote> 元素用于表示对消息引用。

    它的子元素会被渲染为引用的内容。
    """

    pass


@dataclass(repr=False)
class Author(Element):
    """<author> 元素用于表示消息的作者。它的子元素会被渲染为作者的名字。"""

    id: str
    name: str | None = None
    avatar: str | None = None


@dataclass(repr=False)
class Button(Element):
    """<button> 元素用于表示一个按钮。它的子元素会被渲染为按钮的文本。"""

    type: str
    id: str | None = None
    href: str | None = None
    text: str | None = None
    theme: str | None = None

    @classmethod
    def action(cls, button_id: str, theme: str | None = None):
        return Button("action", id=button_id, theme=theme)

    @classmethod
    def link(cls, url: str, theme: str | None = None):
        return Button("link", href=url, theme=theme)

    @classmethod
    def input(cls, text: str, theme: str | None = None):
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


@dataclass(init=False, repr=False)
class Custom(Element):
    """自定义元素用于构造标准元素以外的元素"""

    __names__ = ()

    def __init__(
        self,
        type: str,
        attrs: dict[str, Any] | None = None,
        children: Sequence[str | Element] | None = None,
    ):
        self.type = type
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


@dataclass(repr=False)
class Raw(Element):
    """Raw 元素表示原始文本"""

    content: str

    __names__ = ()

    @override
    def dumps(self, strip: bool = False):
        return self.content if strip else escape(self.content)


def register_element(cls: type[TE], tag: str | None = None) -> type[TE]:
    """注册一个自定义元素类，使其可以被 `transform` 函数识别。

    该类必须继承自 `Element`; 必要时还需要定义 `__names__` 类变量以指定可接受的属性名。
    """
    if not issubclass(cls, Element):
        raise TypeError("cls must be a subclass of Element")
    ELEMENT_TYPE_MAP[tag or cls.__name__.lower()] = cls
    return cls


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


def transform(elements: list[RawElement]) -> list[Element]:
    msg = []
    for elem in elements:
        tag = elem.tag()
        if tag in ELEMENT_TYPE_MAP:
            seg_cls = ELEMENT_TYPE_MAP[tag]
            msg.append(seg_cls.unpack(elem.attrs)(*transform(elem.children)))
        elif tag in ("a", "link"):
            link = Link.unpack(elem.attrs)
            if elem.children:
                link(*transform(elem.children))
            msg.append(link)
        elif tag == "button":
            button = Button.unpack(elem.attrs)
            if elem.children:
                button(*transform(elem.children))
            msg.append(button)
        elif tag in STYLE_TYPE_MAP:
            seg_cls = STYLE_TYPE_MAP[tag]
            msg.append(seg_cls.unpack(elem.attrs)(*transform(elem.children)))
        elif tag in ("br", "newline"):
            msg.append(Br())
        elif tag == "message":
            msg.append(Message.unpack(elem.attrs)(*transform(elem.children)))
        elif tag == "quote":
            msg.append(Quote.unpack(elem.attrs)(*transform(elem.children)))
        else:
            msg.append(Custom(elem.type, elem.attrs)(*transform(elem.children)))
    return msg


@overload
def select(elements: Element | list[Element], query: type[TE]) -> list[TE]: ...


@overload
def select(elements: Element | list[Element], query: str) -> list[Element]: ...


def select(elements: Element | list[Element], query: type[TE] | str):
    if not elements:
        return []
    if isinstance(elements, Element):
        elements = [elements]
    if isinstance(query, str):
        return transform(select_raw("".join(map(str, elements)), query))
    if query is Element:
        return elements
    results = []
    for elem in elements:
        if isinstance(elem, query):
            results.append(elem)
        if elem.children:
            results.extend(select(elem.children, query))
    return results


@final
class _E:
    def __init__(self):
        self.text = Text
        self.at = At
        self.at_role = At.role_
        self.at_all = At.all
        self.sharp = Sharp
        self.link = Link
        self.image = Image.of
        self.audio = Audio.of
        self.video = Video.of
        self.file = File.of
        self.resource = Resource
        self.bold = Bold
        self.italic = Italic
        self.underline = Underline
        self.strikethrough = Strikethrough
        self.spoiler = Spoiler
        self.code = Code
        self.sup = Superscript
        self.sub = Subscript
        self.br = Br
        self.paragraph = Paragraph
        self.message = Message
        self.quote = Quote
        self.author = Author
        self.raw = Raw
        self.button = Button
        self.action_button = Button.action
        self.link_button = Button.link
        self.input_button = Button.input
        self.select = select

    def __call__(self, elem: str, context: dict | None = None) -> Custom:
        """创建一个自定义元素"""
        e = parse(elem, context)[0]
        return Custom(e.type, e.attrs, transform(e.children))


E: Final = _E()
