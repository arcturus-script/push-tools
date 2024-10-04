from .err import catch_exception, AccessFailed
from .push import push
import requests as re


# https://sct.ftqq.com
class server(push):
    url = "https://sctapi.ftqq.com"

    def __init__(self, key):
        super().__init__(key)
        self.url = f"{server.url}/{self.key}.send"

    @catch_exception
    def send(self, msg, title, **kwargs):
        params = {"title": title, "desp": msg}
        options = ["short", "noip", "channel", "openid"]

        for k, v in kwargs.items():
            if k in options:
                params[k] = v

        res = re.post(self.url, params=params).json()

        if res.get("code") == 0:
            self.success()
        else:
            raise AccessFailed(res.get("info"))
