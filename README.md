# satori-python

![latest release](https://img.shields.io/github/release/RF-Tar-Railt/satori-python)
[![Licence](https://img.shields.io/github/license/RF-Tar-Railt/satori-python)](https://github.com/RF-Tar-Railt/satori-python/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/satori-python)](https://pypi.org/project/satori-python)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/satori-python)](https://www.python.org/)

基于 [Satori](https://satori.js.org/zh-CN/) 协议的 Python 开发工具包

## 协议介绍

[Satori Protocol](https://satori.js.org/zh-CN/)

### 协议端

目前提供了 `satori` 协议实现的有：

- [Chronocat](https://chronocat.vercel.app)
- Koishi （搭配 `@koishijs/plugin-server`）

## 安装

安装完整体：
```shell
pip install satori-python
```

只安装基础部分：
```shell
pip install satori-python-core
```

只安装客户端部分：
```shell
pip install satori-python-client
```

只安装服务端部分：
```shell
pip install satori-python-server
```

## 使用

客户端：

```python
from satori import Account, Event, WebsocketsInfo
from satori.client import App

app = App(WebsocketsInfo(port=5140))

@app.register
async def on_message(account: Account, event: Event):
    if event.user and event.user.id == "xxxxxxxxxxx":
        await account.send(event, "Hello, World!")

app.run()
```

服务端：

```python
from satori import Api
from satori.server import Server

server = Server(port=5140)

@server.route(Api.MESSAGE_CREATE)
async def on_message_create(*args, **kwargs):
    return [{"id": "1234", "content": "example"}]

server.run()
```

## 文档

请阅读 [仓库文档](./docs.md)

## 示例

- 客户端：[client.py](./example/client.py)
- 服务端：[server.py](./example/server.py)
  - 服务端(使用适配器)：[server_with_adapter.py](./example/server_with_adapter.py)
- 客户端(webhook)：[client_webhook](./example/client_webhook.py)
- 服务端(webhook)：[server_webhook](./example/server_webhook.py)
- 适配器：[adapter.py](./example/adapter.py)

## 架构

```mermaid
graph LR
    subgraph Server
        server -- run --> asgi
        server -- register --> router -- mount --> asgi
        server -- apply --> provider -- mount  --> asgi
        provider -- event,logins --> server
    end
    subgraph Client
        config -- apply --> app -- run --> network
        app -- register --> listener
        network -- account,event --> listener
        listener -- handle --> account -- session --> api
    end
    
    api -- request --> asgi -- response --> api
    server -- raw-event --> asgi -- websocket/webhook --> network
```
