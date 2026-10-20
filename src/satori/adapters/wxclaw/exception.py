from satori.exception import ActionFailed, NetworkError


class HTTPStatusError(NetworkError):
    def __init__(self, status_code: int, label: str):
        self.status_code = status_code
        super().__init__(f"{label} HTTP {status_code}")


class WxClawActionFailed(ActionFailed):
    def __init__(
        self,
        *,
        ret: int | None = None,
        errcode: int | None = None,
        errmsg: str | None = None,
    ):
        self.ret = ret
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"WxClaw action failed: ret={ret}, errcode={errcode}, errmsg={errmsg!r}")

    def __repr__(self):
        return f"WxClawActionFailed(ret={self.ret}, errcode={self.errcode}, errmsg={self.errmsg!r})"


class SessionExpiredError(WxClawActionFailed):
    pass
