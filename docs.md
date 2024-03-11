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

`satori-python` 使用 `@app.register` 装饰器来增加一个事件处理函数:

```python
from satori.client import App, Account
from satori.model import Event

app = App()

@app.register
async def listen(account: Account, event: Event):
    print(account, event)
```

`@app.register` 需要一个参数为 `Account` 与 `Event` 的异步函数.

- `Account` 对象代表了一个 Satori 平台账号, 你可以使用它来调用 API.
- `Event` 对象代表了一个 Satori 事件, 你可以使用它来获取事件的数据.

## 运行

使用 `App.run` 方法来运行 `App` 对象:

```python
from satori.client import App

app = App()

app.run()
```

`App.run` 可以传入自定义的 `asyncio.AbstractEventLoop` 对象。

## 调用接口

如前所述，`Account` 对象代表了一个 Satori 平台账号，你可以通过其 `session` 属性来调用 API：

```python
from satori.client import App, Account
from satori.model import Event

app = App()

@app.register
async def listen(account: Account, event: Event):
    if event.user.id == "xxxxxx":
        await account.session.send_message(
            event.channel.id,
            "Hello, world!",
        )
```

`Account.session` 拥有现在 `satori` 支持的所有 API 方法。

### 无连接主动发送

`Account` 允许自主创建并请求 api：

```python
from satori.client import Account, ApiInfo

async def main():
    account = Account("kook", "xxxxxxxxxxxxx", ApiInfo(token="xxxx"))
    await account.send_message("xxxxxxxx", "Hello, World!")

```

### 切换服务端地址

`Account` 同样也可以临时切换 api：

```python
from satori.client import App, Account
from satori.model import Event

app = App()

@app.register
async def listen(account: Account, event: Event):
    await account.custom(host="123.456.789.012", port=5140).send(event, "Hello, World!")
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
from satori.const import Api
from satori.server import Server

server = Server()

@server.route(Api.MESSAGE_GET)
async def on_message_get(request):
    return {"id": "123456789", "content": "Hello, world!"}
```

route 填入的若不属于 `Api` 中的枚举值，会被视为是[内部接口](https://satori.js.org/zh-CN/protocol/internal.html)的路由。

同时，你也可以通过 `server.apply` 传入一个满足 `Router` 协议的对象:

```python
from satori.const import Api
from satori.server import Server, Request

server = Server()

class MyRouter:
    def validate_headers(self, headers: dict[str, Any]) -> bool:
        return True

    async def call_api(self, request: Request[Api]):
        if request.action == Api.MESSAGE_GET:
            return {"id": "123456789", "content": "Hello, world!"}

    async def call_internal_api(self, request: Request[str]):
        ...

server.apply(MyRouter())
```

## 事件

事件由 `Provider` 提供:

```python
class Provider(Protocol):
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

from satori import Channel, ChannelType, Event, Login, LoginStatus, Server, User

server = Server()

class MyProvider:
    def authenticate(self, token: str) -> bool:
        return True

    async def get_logins(self):
        return [Login(LoginStatus.ONLINE, self_id="1234567890", platform="example")]

    async def publisher(self):
        seq = 0
        while True:
            await asyncio.sleep(2)
            yield Event(seq, "example", "example", "1234567890", datetime.now(), channel=Channel("1234567890", ChannelType.TEXT), user=User("1234567890"))
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
- `validate_headers`: 验证客户端请求的头部信息.
- `authenticate`: 验证客户端请求的身份信息 (如果平台需要)
- `get_logins`: 获取平台上的登录信息.
- `call_api`: 处理客户端请求的 API 调用.
- `call_internal_api`: 处理客户端请求的内部 API 调用.
- `launch`: 调度逻辑.

## 启动

使用 `Server.run` 方法来运行 `Server` 对象:

```python
from satori.server import Server

server = Server()

server.run()
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
