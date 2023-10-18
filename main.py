from satori.main import App
from satori.config import ClientInfo

app = App(
    ClientInfo(
        port=5500,
        token="9491ee65f2e5322d050021d4ceaca05d42c3ff2fc2a457fdffeb315619bf3f91",
    )
)

@app.register
async def on_message(account, event):
    print(account)
    print(event)


app.run()