from satori import Account, App, Event, WebhookInfo

app = App(WebhookInfo(server_port=12345))


@app.register
async def on_message(account: Account, event: Event):
    print(event)  # noqa: T201
    if event.user and event.user.id == "1234567890":
        await account.session.send_message(event.channel.id, "Hello, World!")


@app.lifecycle
async def record(account, state):
    print(account, state)  # noqa: T201


app.run()
