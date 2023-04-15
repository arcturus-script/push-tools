from .pushplus import Pushplus
from .qmsg import Qmsg
from .server import Server
from .wechat import WorkWechatApp, WorkWechatRobot


class PushComposite:
    def __init__(self) -> None:
        self.children = {}

    def add(self, key: str, push) -> None:
        self.children[key] = push

    def send(self, msg: str, **kwargs) -> None:
        for push in self.children.values():
            push.send(msg, **kwargs)

    def remove(self, key: str) -> None:
        self.children.pop(key)


class PushSender:
    def __init__(self, type: str, key) -> None:
        self.push = self.create(type, key)

    def create(self, type: str, key):
        if type == "pushplus":
            return Pushplus(key)
        elif type == "server":
            return Server(key)
        elif type == "qmsg":
            return Qmsg(key)
        elif type == "workWechatRobot":
            return WorkWechatRobot(key)
        elif type == "workWechat":
            return WorkWechatApp(key)

    def send(self, msg: str, **kwargs):
        self.push.send(msg, **kwargs)
