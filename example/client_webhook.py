from satori import Account, Event, WebhookInfo
from satori.client import App

app = App(WebhookInfo(server_port=12345, path="bar"))


@app.register
async def on_message(account: Account, event: Event):
    if event.user and event.user.id == "1234567890":
        print(await account.session.channel_get(event.channel.id))  # noqa: T201
        await account.session.send_message(event.channel.id, "Hello, World!")


@app.lifecycle
async def record(account, state):
    print(account, state)  # noqa: T201


app.run()
