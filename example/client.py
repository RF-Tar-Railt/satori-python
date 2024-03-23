from satori import WebsocketsInfo
from satori.client import Account, App
from satori.event import MessageEvent

app = App(WebsocketsInfo(port=12345, path="foo"))


@app.register
async def on_message(account: Account, event: MessageEvent):
    if event.user and event.user.id == "9876543210":
        print(await account.session.channel_get(event.channel.id))  # noqa: T201
        print(await account.session.send_message(event.channel, "Hello, World!"))  # noqa: T201


@app.lifecycle
async def record(account: Account, state):
    print(account, state)  # noqa: T201


app.run()
