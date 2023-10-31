from satori import Account, App, ClientInfo, Event

app = App(ClientInfo(port=12345, path="foo"))


@app.register
async def on_message(account: Account, event: Event):
    if event.user and event.user.id == "1234567890":
        print(await account.session.channel_get(event.channel.id))  # noqa: T201
        await account.session.send_message(event.channel, "Hello, World!")


@app.lifecycle
async def record(account: Account, state):
    print(account, state)  # noqa: T201


app.run()
