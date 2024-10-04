from .err import catch_exception, AccessFailed
from .push import push
import requests as re


# https://qmsg.zendee.cn/
class qmsg(push):
    url = "https://qmsg.zendee.cn"

    def __init__(self, key):
        super().__init__(key)
        self.url = f"{qmsg.url}/send/{key}"

    @catch_exception
    def send(self, msg, **kwargs) -> None:
        params = {"msg": msg}
        options = ["qq", "bot"]

        for k, v in kwargs.items():
            if k in options:
                params[k] = v

        res = re.post(self.url, params=params).json()

        if res.get("code") == 0:
            self.success()
        else:
            raise AccessFailed(res.get("reason"))
