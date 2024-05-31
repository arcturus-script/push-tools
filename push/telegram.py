from .decorator import catchException
from .push import Push
import requests as re


class Telegram(Push):

    url = "https://api.telegram.org"

    def __init__(self, key: dict) -> None:
        super().__init__(key)

    @catchException
    def send(self, msg: str, **kwargs) -> None:
        
        params = {
            "text": msg
        }

        token = self.key.get("token")

        chat_id = self.key.get("chat_id")

        if chat_id:
            params.update({"chat_id": chat_id})

        res = re.post(f"{self.url}/bot{token}/sendMessage", params=params).json()

        if res.get("ok") == True:
            self.success()
        else:
            raise Exception(res.get("description"))
