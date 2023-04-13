from .decorator import catchException
from .push import Push
import requests as re

params = ("title", "channel", "topic", "webhook", "template")


def isParams(k: str) -> bool:
    return k in params


class Pushplus(Push):
    """
    offical address: https://www.pushplus.plus
    """

    url = "http://www.pushplus.plus/send"

    def __init__(self, key: str):
        super().__init__(key)

    @catchException
    def send(self, msg: str, **kwargs):
        params = {
            "token": self.key,
            "content": msg,
        }

        for keys, values in kwargs.items():
            if isParams(keys):
                params.update({keys: values})

        res = re.post(self.url, json=params).json()

        if res.get("code") == 200:
            self.success()
        else:
            raise Exception(res.get("msg"))
