# 客户端

## 初始化

一个 `satori-python` 客户端的构建从创建 `App` 对象开始:

```python
from satori.client import App

app = App()
```

## 配置

一个配置对应了一个 Satori 连接:

```python
class WebsocketsInfo(Config):
    host: str = "localhost"
    port: int = 5140
    token: Optional[str] = None
```

或

```python
class WebhookInfo(Config):
    path: str = "v1/events"
    host: str = "127.0.0.1"
    port: int = 8080
    token: Optional[str] = None
    server_host: str = "localhost"
    server_port: int = 5140
```

你可以在创建 `App` 对象时传入一个或多个 `WebsocketsInfo` 或 `WebhookInfo` 对象:

```python
from satori.client import App
from satori.config import WebsocketsInfo, WebhookInfo

app = App(
    WebsocketsInfo(...),
    WebhookInfo(...),
)
```

或使用 `App.apply` 方法:

```python
from satori.client import App
from satori.config import WebsocketsInfo, WebhookInfo

app = App()
app.apply(WebsocketsInfo(...))
app.apply(WebhookInfo(...))
```

同时你可以自己定义新的 `Config`，只需要实现下面几类方法即可:

```python
class Config:
    @property
    def identity(self) -> str:
        raise NotImplementedError

    @property
    def api_base(self) -> URL:
        raise NotImplementedError
```

然后在 App 注册对应的 Network：

```python
from satori.client import App

App.register_config(YourConfig, YourNetwork)
```

## 订阅

`satori-python` 使用 `@app.register` 装饰器来增加一个通用事件处理函数:

```python
from satori.client import App, Account
from satori.model import Event

app = App()

@app.register
async def listen(account: Account, event: Event):
    print(account, event)
```

`@app.register` 需要一个参数为 `Account` 与 `Event` 的异步函数.

- `Account` 对象代表了接受事件的 Satori 平台账号, 你可以使用它来调用 API.
- `Event` 对象代表了任意类型的 Satori 事件, 你可以使用它来获取事件的数据.

除此之外，你可以使用 `@app.register_on` 装饰器来增加一个确定事件类型的处理函数:

```python
from satori import EventType
from satori.client import App, Account
from satori.event import MessageEvent

app = App()

@app.register_on(EventType.MESSAGE_CREATED)
async def listen(account: Account, event: MessageEvent):
    print(account, event)
```


## 运行

使用 `App.run` 方法来同步运行 `App` 对象:

```python
from satori.client import App

app = App()

app.run()
```

或使用 `App.run_async` 方法来异步运行 `App` 对象:

```python
from satori.client import App

app = App()

async def main():
    await app.run_async()

...
```


`App.run` 可以传入自定义的 `asyncio.AbstractEventLoop` 对象。

## 调用接口

如前所述，`Account` 对象代表了一个 Satori 平台账号，你可以通过其 `protocol` 属性来调用 API：

```python
from satori.client import App, Account
from satori.model import Event

app = App()

@app.register
async def listen(account: Account, event: Event):
    if event.user.id == "xxxxxx":
        await account.protocol.send_message(
            event.channel.id,
            "Hello, world!",
        )
```

`Account.protocol` 拥有现在 `satori` 支持的所有 API 方法。

### 无连接主动发送

`Account` 允许自主创建并请求 api：

```python
from satori import Login
from satori.client import Account, ApiInfo

async def main():
    account = Account("kook", "xxxxxxxxxxxxx", Login(...), ApiInfo(token="xxxx"))
    await account.send_message("xxxxxxxx", "Hello, World!")

```

### 切换服务端地址或使用自定义接口

`Account` 可以临时切换 api：

```python
from satori.client import App, Account
from satori.client.protocol import ApiProtocol
from satori.model import Event

app = App()

@app.register
async def listen(account: Account, event: Event):
    await account.custom(host="123.456.789.012", port=5140).send(event, "Hello, World!")

class MyProtocol(ApiProtocol):
    async def my_api(self, event, *args): ...

@app.register
async def listen(account: Account, event: Event):
    my_account = account.custom(protocol_cls=MyProtocol)
    await my_account.protocol.my_api(event, "Hello, World!")
```

# 服务端

## 初始化

一个 `satori-python` 服务端的构建从创建 `Server` 对象开始:

```python
from satori.server import Server

server = Server()
```

## 配置

server 的配置直接在构造时传入：

```python
from satori.server import Server

server = Server(
    host="0.0.0.0",
    port=8080,
)
```

同时可以传入 webhook 目标：

```python
from satori.config import WebhookInfo
from satori.server import Server

server = Server(
    webhooks=[WebhookInfo(port=8080)]
)
```

## 路由

你可以使用 `Server.route` 方法来自定义路由:

```python
from satori import MessageObject
from satori.const import Api
from satori.server import Server, Request, route

server = Server()

@server.route(Api.MESSAGE_CREATE)
async def on_message_create(request: Request[route.MESSAGE_CREATE]):
    return [MessageObject(id="123456789", content="Hello, world!")]
```

route 填入的若不属于 `Api` 中的枚举值，会被视为是[内部接口](https://satori.js.org/zh-CN/protocol/internal.html)的路由。

route 装饰的函数的返回值既可以是 satori 中的模型，也可以是原始数据。

同时，你也可以通过 `server.apply` 传入一个满足 `Router` 协议的对象，这里推荐继承 `RouterMixin` 类来实现路由:

```python
from satori import MessageObject
from satori.const import Api
from satori.server import Server, Request, RouterMixin, route

server = Server()

class MyRouter(RouterMixin):
    def __init__(self):
        self.routes = {}
        
        @self.route(Api.MESSAGE_CREATE)
        async def on_message_create(request: Request[route.MESSAGE_CREATE]):
            return [MessageObject(id="123456789", content="Hello, world!")]

server.apply(MyRouter())
```

## 事件

事件由 `Provider` 提供:

```python
class Provider(Protocol):
    @property
    def id(self): ...
    
    def publisher(self) -> AsyncIterator[Event]:
        ...

    def authenticate(self, token: str) -> bool:
        ...

    async def get_logins(self) -> list[Login]:
        ...
```

你可以通过 `server.apply` 传入一个满足 `Provider` 协议的对象:

```python
import asyncio
from datetime import datetime

from satori import Channel, ChannelType, Event, Login, LoginStatus, User
from satori.server import Server

server = Server()

class MyProvider:
    @property
    def id(self):
        return "example"

    def authenticate(self, token: str) -> bool:
        return True

    async def get_logins(self):
        return [Login(LoginStatus.ONLINE, self_id="1234567890", platform="example")]

    async def publisher(self):
        seq = 0
        while True:
            await asyncio.sleep(2)
            yield Event(seq, "example", "example", "1234567890", datetime.now(), channel=Channel("1234567890", ChannelType.TEXT), user=User("9876543210"))
            seq += 1

server.apply(MyProvider())
```

## 适配器

适配器是一个特殊的类，它同时实现了 `Provider` 和 `Router` 协议。

```python
from satori.server import Server, Adapter

server = Server()
server.apply(Adapter(...))
```

### 必需方法

一个适配器需要实现以下方法:

- `get_platform`: 返回适配器所适配的平台名称.
- `publisher`: 用于推送平台事件.
- `ensure`: 验证客户端请求的`platform` 和 `self-id`.
- `authenticate`: 验证客户端请求的身份信息 (如果平台需要)
- `get_logins`: 获取平台上的登录信息.
- `launch`: 调度逻辑.

## 启动

使用 `Server.run` 方法来运行 `Server` 对象:

```python
from satori.server import Server

server = Server()

server.run()
```

或使用 `Server.run_async` 方法来异步运行 `Server` 对象:

```python
from satori.server import Server

server = Server()

async def main():
    await server.run_async()

...
```

# 消息元素

`satori-python` 使用 `Element` 类来表示 Satori 消息元素.

## 基本类型

- `Text`: 文本类型，对应 [纯文本](https://satori.js.org/zh-CN/protocol/elements.html#%E7%BA%AF%E6%96%87%E6%9C%AC).
- `At`: 提及用户类型，对应 [提及用户](https://satori.js.org/zh-CN/protocol/elements.html#%E6%8F%90%E5%8F%8A%E7%94%A8%E6%88%B7).
- `Sharp`: 提及频道类型，对应 [提及频道](https://satori.js.org/zh-CN/protocol/elements.html#%E6%8F%90%E5%8F%8A%E9%A2%91%E9%81%93).
- `Link`: 链接类型，对应 [链接](https://satori.js.org/zh-CN/protocol/elements.html#%E9%93%BE%E6%8E%A5).

```python
from satori import Text, At, Sharp, Link

a = Text("1234")
role = At.role_("admin")
chl = Sharp("abcd")
link = Link("www.baidu.com")
link1 = Link("github.com/RF-Tar-Railt/satori-python")(
    "satori-python"
)
```

## 资源类型

- `Image`, `Audio`, `Video`, `File`: 资源类型，对应 [资源元素](https://satori.js.org/zh-CN/protocol/elements.html#%E8%B5%84%E6%BA%90%E5%85%83%E7%B4%A0).

资源类型元素可以用特殊的 `.of` 方法来创建:

```python
from satori import Image

image = Image.of(url="https://example.com/image.png")
```

在 `.of` 方法中，你可以传入以下参数:

- `url`: 资源的 URL.
- `path`: 资源的本地路径.
- `raw`: 资源的二进制数据. 会要求同时传入 `mime` 参数.

```python
from satori import Image
from io import BytesIO
from PIL import Image as PILImage

img = PILImage.open("image.png")
data = BytesIO()
img.save(data, format="PNG")

image = Image.of(raw=data, mime="image/png")
```

## 修饰类型

- `Bold`, `Italic`, `Underline`, `Strikethrough`, ...: 修饰类型，对应 [修饰元素](https://satori.js.org/zh-CN/protocol/elements.html#%E4%BF%AE%E9%A5%B0%E5%85%83%E7%B4%A0).

```python
from satori import Bold, Italic, Underline, Paragraph

text = Bold(
    "hello",
    Italic("world,"),
    Underline()(
        "Satori!"
    ),
    Paragraph("This is a paragraph.")
)
```

## 排版类型

- `Br`: 换行类型，对应 [换行](https://satori.js.org/zh-CN/protocol/elements.html#%E6%8D%A2%E8%A1%8C).
- `Paragraph`: 段落类型，对应 [段落](https://satori.js.org/zh-CN/protocol/elements.html#%E6%AE%B5%E8%90%BD).
- `Message`: 渲染消息，对应 [消息](https://satori.js.org/zh-CN/protocol/elements.html#%E6%B6%88%E6%81%AF).

对于 `Message`，你可以通过 `content` 参数来传入子元素:

```python
from satori import Message, Author

message = Message(forward=True)(
    Message(id="123456789"),
    Message(id="987654321"),
    Message(
        content=[
            Author(id="123456789"),
            "Hello, "
        ]
    ),
    Message()(
        Author(id="123456789"),
        "World!"
    )
)
```

**！！！Satori 下的Message 不是“消息序列”的概念！！！**

## 元信息类型

- `Author`: 作者类型，对应 [作者](https://satori.js.org/zh-CN/protocol/elements.html#%E4%BD%9C%E8%80%85).
- `Quote`: 引用类型，对应 [引用](https://satori.js.org/zh-CN/protocol/elements.html#%E5%BC%95%E7%94%A8).

`Quote` 的用法与 `Message` 一致。

## 特殊类型

- `Custom`: 用来构造 Satori 标准外的消息元素。
- `Raw`: 用来构造 Satori 标准外的消息元素，直接传入文本。

## 特殊方法

`satori-python` 提供了一个方法 `select`, 用来递归地从消息中遍历提取特定类型的元素:

```python
from satori import Quote, Author, Text, select

msg = [Quote(id="12345678")(Author(id="987654321"), Text("Hello, World!")), Text("Hello, World!")]
authors = select(msg, Author)
```


# 资源链接

参考：[`资源链接(实验性)`](https://satori.js.org/zh-CN/advanced/resource.html)

## 上传

对于客户端，你可以使用 `Account.upload` 方法来上传资源:

```python
from pathlib import Path
from satori.client import App, Account, Event
from satori.model import Upload


app = App()

@app.register
async def _(account: Account, event: Event):
    # 直接构造 Upload 对象并传入，返回`资源链接`的列表
    resp: list[str] = await account.upload(
        Upload(file=b'...'),
        Upload(file=Path("path/to/file")),
    )
    # 或者构造 Upload 对象并使用关键字传入，返回`资源链接`的字典，键为传入的关键字
    resp: dict[str, str] = await account.upload(
        foo=Upload(file=b'...'),
        bar=Upload(file=Path("path/to/file")),
    )
```

对于服务端，你可以通过注册 `upload.create` 路由来处理上传请求:

```python
from satori.const import Api
from satori.server import Server, Request, FormData, parse_content_disposition

server = Server()

@server.route(Api.UPLOAD_CREATE)
async def on_upload_create(request: Request[FormData]):
    # 上传的文件在 `request.params` 中
    res = {}
    for _, data in request.params.items():
        if isinstance(data, str):
            continue
        ext = data.headers["content-type"]
        disp = parse_content_disposition(data.headers["content-disposition"])
        res[disp["name"]] = ...  # 处理后的资源链接
    return res
```

## 下载

对于客户端，推荐使用 `Account.protocol.download` 方法来下载资源:

```python
from satori.client import App, Account, Event
from satori import Image, Upload


app = App()

@app.register
async def _(account: Account, event: Event):
    # 假设你获取到了一个 Image 对象, 你想要下载这个资源
    img: Image = ...
    # 那么你可以传入 `Image.src` 来下载资源
    data: bytes = await account.protocol.download(img.src)
    # 或者你想下载你通过 `Account.upload` 上传的资源
    url = (await account.upload(Upload(file=b'...')))[0]
    data: bytes = await account.protocol.download(url)
    # 或者你直接传入一个合法的 url
    data: bytes = await account.protocol.download("https://example.com/image.png")
```

若链接符合以下条件之一，则返回链接的代理形式 ({host}/{path}/{version}/proxy/{url})：
- 链接以 "upload://" 开头
- 链接开头出现在 account.self_info.proxy_urls 中的某一项

对于服务端：
- 如果 url 不是合法的 URL，会直接返回 400；
- 如果 url 不以任何一个 Adapter.proxy_urls 中的前缀开头，会直接返回 403；
- 如果 url 是一个内部链接，会由该内部链接的实现决定如何提供此资源 (可能的方式包括返回数据、重定向以及资源无法访问的报错)；
- 如果 url 是一个外部链接 (即不以 upload:// 开头的链接)，会在 SDK 侧下载该资源并返回 (通常使用流式传输)

你可以通过实现 `download_uploaded` 方法和 `download_proxied` 方法来处理内部链接和外部链接的下载请求:

```python
from satori.server import Server, Provider

class MyProvider(Provider):
    # 此处声明的 `proxy_urls` 会同步到 Login.proxy_urls 中
    @staticmethod
    def proxy_urls() -> list[str]:
        return ["https://example.com"]

    async def download_uploaded(self, platform: str, self_id: str, path: str) -> bytes:
        # 处理下载请求
        return b"..."
    
    # prefix 为 Adapter.proxy_urls 中的某一项
    # Adapter 类下 download_proxied 已有默认实现，你可以选择自己重写实现
    async def download_proxied(self, prefix: str, url: str) -> bytes:
        # 处理下载请求
        return b"..."

# 当 download 返回值的大小超过 stream_limit 时，会启用流式传输。默认为 16MB
server = Server(stream_limit=4 * 1024 * 1024)

server.apply(MyProvider())

server.run()
```
