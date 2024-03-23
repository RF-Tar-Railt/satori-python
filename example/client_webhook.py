from satori import WebhookInfo
from satori.client import Account, App
from satori.event import MessageEvent

app = App(WebhookInfo(server_port=12345, path="bar"))


@app.register
async def on_message(account: Account, event: MessageEvent):
    if event.user and event.user.id == "1234567890":
        print(await account.session.channel_get(event.channel.id))  # noqa: T201
        await account.session.send_message(event.channel.id, "Hello, World!")


@app.lifecycle
async def record(account, state):
    print(account, state)  # noqa: T201


app.run()
