from satori import Server
from adapter import ExampleAdapter


server = Server(host="localhost", port=12345)
server.apply(ExampleAdapter())

server.run()
