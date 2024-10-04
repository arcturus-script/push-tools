from .err import catch_exception, AccessFailed
from .push import push
import requests as re


# https://www.pushplus.plus
class pushplus(push):
    # 请求地址
    url = "http://www.pushplus.plus/send"

    def __init__(self, key):
        super().__init__(key)

    # 消息接口
    @catch_exception
    def send(self, msg, **kwargs):
        params = {
            "token": self.key,
            "content": msg,
        }

        # 请求参数
        options = [
            "title",
            "topic",
            "template",
            "channel",
            "webhook",
            "callbackUrl",
            "timestamp",
            "to",
            "pre",
        ]

        for key, value in kwargs.items():
            if key in options:
                params[key] = value

        res = re.post(self.url, json=params).json()

        if res.get("code") == 200:
            self.success()
        else:
            raise AccessFailed(res.get("msg"))
