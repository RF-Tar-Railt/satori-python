from satori import EventType
from satori.client import Account, App, WebhookInfo
from satori.event import MessageEvent

app = App(WebhookInfo(server_port=12345, path="bar"))


@app.register_on(EventType.MESSAGE_CREATED)
async def on_message(account: Account, event: MessageEvent):
    if event.user and event.user.id == "9876543210":
        print(await account.channel_get(event.channel.id))  # noqa: T201
        await account.send_message(event.channel.id, "Hello, World!")


@app.lifecycle
async def record(account, state):
    print(account, state)  # noqa: T201


app.run()
