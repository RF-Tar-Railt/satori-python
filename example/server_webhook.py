from adapter import ExampleAdapter

from satori import Server, WebhookInfo

server = Server(host="localhost", port=12345, webhooks=[WebhookInfo(host="localhost")])
server.apply(ExampleAdapter())

server.run()
