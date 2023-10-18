# 客户端

## 初始化

一个 `satori-python` 客户端的构建从创建 `App` 对象开始:

```python
from satori import App

app = App()
```

## 配置

一个配置对应了一个 Satori 连接:

```python
class ClientInfo(Config):
    host: str = "localhost"
    port: int = 5140
    token: Optional[str] = None
```

或

```python
class WebhookInfo(Config):
    self_host: str = "127.0.0.1"
    self_port: int = 8080
    host: str = "localhost"
    port: int = 5140
    token: Optional[str] = None
```

你可以在创建 `App` 对象时传入一个或多个 `ClientInfo` 或 `WebhookInfo` 对象:

```python
from satori import App, ClientInfo, WebhookInfo

app = App(
    ClientInfo(...),
    WebhookInfo(...),
)
```

或使用 `App.apply` 方法:

```python
from satori import App, ClientInfo

app = App()
app.apply(ClientInfo(...))
app.apply(ClientInfo(...))
```

## 订阅

`satori-python` 使用 `@app.register` 装饰器来增加一个事件处理函数:

```python
from satori import App, Account, Event

app = App()

@app.register
async def listen(account: Account, event: Event):
    print(event)
```

`@app.register` 需要一个参数为 `Account` 与 `Event` 的异步函数.
- `Account` 对象代表了一个 Satori 平台账号, 你可以使用它来调用 API.
- `Event` 对象代表了一个 Satori 事件, 你可以使用它来获取事件的数据.

## 运行

使用 `App.run` 方法来运行 `App` 对象:

```python
from satori import App

app = App()

app.run()
```

`App.run` 可以传入自定义的 `asyncio.AbstractEventLoop` 对象。

## 调用接口

如前所述，`Account` 对象代表了一个 Satori 平台账号，你可以使用它来调用 API：

```python
from satori import App, Account, Event

app = App()

@app.register
async def listen(account: Account, event: Event):
    if event.user.id == "xxxxxx":
        await account.send_message(
            event.channel.id,
            "Hello, world!",
        )
```

`Account` 拥有现在 `satori` 支持的所有 API 方法。

# 服务端

## 初始化

一个 `satori-python` 服务端的构建从创建 `Server` 对象开始:

```python
from satori import Server

server = Server()
```

## 配置

server 的配置直接在构造时传入:

```python
from satori import Server

server = Server(
    host="0.0.0.0",
    port=8080,
)
```

## 适配器

server 依靠适配器来连接不同的平台:

```python
from satori import Server, Adapter

server = Server()
server.apply(Adapter(...))
```

### 必需方法

一个适配器需要实现以下方法:
- `get_platform`: 返回适配器所适配的平台名称.
- `bind_event_callback`: 绑定事件回调函数，用于发布平台事件.
- `validate_headers`: 验证客户端请求的头部信息.
- `authenticate`: 验证客户端请求的身份信息 (如果平台需要)
- `get_logins`: 获取平台上的登录信息.
- `call_api`: 处理客户端请求的 API 调用.
- `launch`: 调度逻辑.

## 启动

使用 `Server.run` 方法来运行 `Server` 对象:

```python
from satori import Server

server = Server()

server.run()
```

## 自定义路由

你可以使用 `Server.override` 方法来自定义路由:

```python
from satori import Server

server = Server()

@server.override("message.create")
async def index(headers, body):
    return {"id": "123456789", "content": "Hello, world!"}
```

# 消息元素

`satori-python` 使用 `Element` 类来表示 Satori 消息元素.

## 基本类型

- `Text`: 文本类型，对应 [纯文本](https://satori.js.org/zh-CN/protocol/elements.html#%E7%BA%AF%E6%96%87%E6%9C%AC).
- `At`: 提及用户类型，对应 [提及用户](https://satori.js.org/zh-CN/protocol/elements.html#%E6%8F%90%E5%8F%8A%E7%94%A8%E6%88%B7).
- `Sharp`: 提及频道类型，对应 [提及频道](https://satori.js.org/zh-CN/protocol/elements.html#%E6%8F%90%E5%8F%8A%E9%A2%91%E9%81%93).
- `Link`: 链接类型，对应 [链接](https://satori.js.org/zh-CN/protocol/elements.html#%E9%93%BE%E6%8E%A5).

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

## 排版类型

- `Br`: 换行类型，对应 [换行](https://satori.js.org/zh-CN/protocol/elements.html#%E6%8D%A2%E8%A1%8C).
- `Paragraph`: 段落类型，对应 [段落](https://satori.js.org/zh-CN/protocol/elements.html#%E6%AE%B5%E8%90%BD).
- `Message`: 渲染消息，对应 [消息](https://satori.js.org/zh-CN/protocol/elements.html#%E6%B6%88%E6%81%AF).

对于 `Message`，你可以通过 `content` 参数来传入子元素:

```python
from satori import Message, Author, Text

message = Message(
    forward=True,
    content=[
        Message(id="123456789"),
        Message(id="987654321"),
        Message(
            content=[
                Author(id="123456789"),
                Text("Hello, world!"),
            ]
        ),
    ]
)
```

## 元信息类型

- `Author`: 作者类型，对应 [作者](https://satori.js.org/zh-CN/protocol/elements.html#%E4%BD%9C%E8%80%85).
- `Quote`: 引用类型，对应 [引用](https://satori.js.org/zh-CN/protocol/elements.html#%E5%BC%95%E7%94%A8).

`Quote` 的用法与 `Message` 一致。
