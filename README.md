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

```shell
pip install satori-python
```

## 使用

客户端：
```python
from satori import App, Account, Event, ClientInfo

app = App(ClientInfo(port=5140))

@app.register
async def on_message(account: Account, event: Event):
    if event.user and event.user.id == "xxxxxxxxxxx":
        await account.send(event, "Hello, World!")

app.run()
```

服务端：
```python
from satori import Server, Adapter

server = Server(port=5140)
server.apply(Adapter())
server.run()
```

## 文档

请阅读 [仓库文档](./docs.md)

## 示例

- 客户端：[client.py](./example/client.py)
- 服务端：[server.py](./example/server.py)
- 适配器：[adapter.py](./example/adapter.py)
