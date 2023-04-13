from .decorator import catchException
from .push import Push
import requests as re


class Server(Push):
    """
    offical address: https://sct.ftqq.com
    """

    url = "https://sctapi.ftqq.com"

    def __init__(self, key: str) -> None:
        super().__init__(key)

    @catchException
    def send(self, msg: str, **kwargs) -> None:
        params = {
            "title": kwargs.get("title", "No title"),
        }

        channel = kwargs.get("channel")

        if channel:
            params.update({"channel": channel})

        params.update({"desp": msg})

        openid = kwargs.get("openid")

        if openid:
            params.update({"openid": openid})

        res = re.post(f"{self.url}/{self.key}.send", params=params).json()

        if res.get("code") == 0:
            self.success()
        else:
            raise Exception(res.get("info"))
