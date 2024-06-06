from satori import EventType, Upload, WebsocketsInfo
from satori.client import Account, App
from satori.event import MessageEvent

app = App(WebsocketsInfo(port=12345, path="foo"))


@app.register_on(EventType.MESSAGE_CREATED)
async def on_message(account: Account, event: MessageEvent):
    if event.user and event.user.id == "9876543210":
        print(await account.session.channel_get(event.channel.id))  # noqa: T201
        print(await account.session.send_message(event.channel, "Hello, World!"))  # noqa: T201
    print(  # noqa: T201
        res := await account.upload(
            Upload(
                b"1234",
                name="foo.png",
            )
        )
    )
    print(await account.session.download(res[0]))  # noqa: T201


@app.lifecycle
async def record(account: Account, state):
    print(account, state)  # noqa: T201


app.run()
