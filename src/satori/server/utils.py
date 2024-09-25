import ssl
from collections import deque


class Deque:
    def __init__(self, maxlen: int):
        self.data = deque(maxlen=maxlen)
        self.offset = 0

    def append(self, x):
        if len(self.data) == self.data.maxlen:
            self.offset += 1
        self.data.append(x)

    def __getitem__(self, i: int):
        index = i - self.offset
        if index < 0 or index >= len(self.data):
            return
        return self.data[index]

    def after(self, i: int):
        if i < self.offset:
            i = self.offset - 1
        return list(self.data)[i + 1 - self.offset :]


ctx = ssl.create_default_context()
ctx.set_ciphers("DEFAULT")


if __name__ == "__main__":
    d = Deque(3)
    d.append(0)
    d.append(1)
    d.append(2)
    d.append(3)
    d.append(4)
    d.append(5)
