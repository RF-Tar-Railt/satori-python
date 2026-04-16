import socket


def get_public_ip():
    st = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        st.connect(("10.255.255.255", 1))
        IP = st.getsockname()[0]
    except Exception:
        IP = "localhost"
    finally:
        st.close()
    return IP


try:
    from msgspec.json import Decoder, Encoder  # noqa: F401

    decoder = Decoder()
    encoder = Encoder()

    decode = decoder.decode

    def encode(obj):
        return encoder.encode(obj).decode()

    def encode_bytes(obj):
        return encoder.encode(obj)

except ImportError:
    import json

    def encode(obj):
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

    def encode_bytes(obj):
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    decode = json.loads
