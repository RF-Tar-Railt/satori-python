from adapter import ExampleAdapter

from satori import Server

server = Server(host="localhost", port=12345)
server.apply(ExampleAdapter())

server.run()
