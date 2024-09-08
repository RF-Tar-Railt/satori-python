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


if __name__ == "__main__":
    print(get_public_ip())  # noqa: T201
