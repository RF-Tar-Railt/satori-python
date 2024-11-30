from satori import EventType, Upload, WebsocketsInfo
from satori.client import Account, App
from satori.event import Event, MessageEvent

app = App(WebsocketsInfo(port=12345, path="foo"))


@app.register
async def _(account: Account, event: Event):
    print(event.id)  # noqa: T201


@app.register_on(EventType.MESSAGE_CREATED)
async def on_message(account: Account, event: MessageEvent):
    print(event.message)  # noqa: T201
    if event.user and event.user.id == "9876543210":
        print(await account.channel_get(event.channel.id))  # noqa: T201
        print(await account.send_message(event.channel, "Hello, World!"))  # noqa: T201
        print(  # noqa: T201
            res := await account.upload(
                Upload(
                    b"1234",
                    name="foo.png",
                )
            )
        )
        print(await account.download(res[0]))  # noqa: T201


@app.lifecycle
async def record(account: Account, state):
    print(account, state)  # noqa: T201


app.run()
