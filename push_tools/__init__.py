from .pushplus import pushplus
from .qmsg import qmsg
from .server import server
from .wechat import workWechat, workWechatRobot

push_server = {
    "pushplus": pushplus,
    "server": server,
    "qmsg": qmsg,
    "workWechatRobot": workWechatRobot,
    "workWechat": workWechat,
}


class push_composite:
    def __init__(self):
        self.children = {}

    def add(self, key, push):
        self.children[key] = push

    def send(self, msg, **kwargs):
        for push in self.children.values():
            push.send(msg, **kwargs)

    def remove(self, key):
        self.children.pop(key)


class push_creator:
    def __init__(self, type, key):
        self.push = self.create(type, key)

    def create(self, type, key):
        if type not in push_server:
            print(f"Unsupported push type: {type}")
            return None

        return push_server[type](key)

    def send(self, msg, **kwargs):
        if self.push is not None:
            self.push.send(msg, **kwargs)
        else:
            print("No push instance created.")
