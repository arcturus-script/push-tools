from tools.decorator import catchException
from push import Push
import requests as re


class Qmsg(Push):
    """
    offical address: https://qmsg.zendee.cn/api
    """

    url = f"https://qmsg.zendee.cn:443/send"

    def __init__(self, key: str) -> None:
        super().__init__(key)

    @catchException
    def send(self, msg: str) -> None:
        params = {
            "msg": msg,
        }

        res = re.get(f"{self.url}/{self.key}", params=params).json()

        if res.get("code") == 0:
            print("Message sent successfully.")
        else:
            raise Exception(res.get("reason"))
