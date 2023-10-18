from satori import Account, App, ClientInfo, Event

app = App(ClientInfo(port=12345))


@app.register
async def on_message(account: Account, event: Event):
    print(event)
    if event.user and event.user.id == "1234567890":
        await account.send_message(event.channel.id, "Hello, World!")


app.run()
