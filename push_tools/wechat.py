from .err import catch_exception, AccessFailed
from .push import push
import requests as re


# 内部应用开发文档 (https://developer.work.weixin.qq.com/document/path/90664)
# 相关参数获取方法 (https://developer.work.weixin.qq.com/document/path/90665)
class workWechat(push):
    token = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"

    def __init__(self, key):
        super().__init__(key)

    @catch_exception
    def get_access_token(self):
        corpSecret = self.key["corpSecret"]
        corid = self.key["corpid"]

        params = {"corpid": corid, "corpsecret": corpSecret}

        res = re.get(self.token, params).json()

        if res.get("errcode") == 0:
            return res.get("access_token")
        else:
            raise AccessFailed(res.get("errmsg"))

    # 文本消息
    def send(self, msg, agentid, **kwargs):
        msgtype = kwargs.get("msgtype", "text")

        body = {"msgtype": msgtype, msgtype: {"content": msg}, "agentid": agentid}

        options = {
            "touser": "@all",
            "toparty": "",
            "totag": "",
            "safe": 0,
            "enable_id_trans": 0,
            "enable_duplicate_check": 0,
            "duplicate_check_interval": 1800,
        }

        for k, v in options.items():
            if k in kwargs:
                body[k] = v
            else:
                body[k] = options[k]

        self.raw_send(body)

    @catch_exception
    def raw_send(self, body):
        params = {"access_token": self.get_access_token()}

        res = re.post(self.url, params=params, json=body).json()

        errcode = res.get("errcode")

        if errcode == 0:
            self.success()
        else:
            raise AccessFailed(res.get("errmsg"))


# https://developer.work.weixin.qq.com/document/path/91770
class workWechatRobot(push):
    url = "https://qyapi.weixin.qq.com/cgi-bin/webhook"

    def __init__(self, key):
        super().__init__(key)
        self.surl = f"{workWechatRobot.url}/send"
        self.uurl = f"{workWechatRobot.url}/upload_media"

    def send(self, msg, **kwargs):
        msgtype = kwargs.get("msgtype")

        if msgtype == "markdown":
            self._markdown(msg)
        else:
            self._text(msg, **kwargs)

    @catch_exception
    def raw_send(self, body):
        res = re.post(self.surl, params={"key": self.key}, json=body).json()

        errcode = res.get("errcode")

        if errcode == 0:
            self.success()
        else:
            raise AccessFailed(res.get("errmsg"))

    def _text(self, content, **kwargs):
        options = ["mentioned_list", "mentioned_mobile_list"]
        body = {"content": content}

        for k, v in kwargs.items():
            if k in options:
                body[k] = v

        self.raw_send({"msgtype": "text", "text": body})

    def _markdown(self, content):
        self.raw_send({"msgtype": "markdown", "markdown": {"content": content}})

    @catch_exception
    def upload(self, type, file):
        res = re.post(
            self.uurl,
            params={
                "key": self.key,
                "type": type,
            },
            files={"file": file},
        ).json()

        errcode = res.get("errcode")

        if errcode == 0:
            return res.get("media_id")
        else:
            raise AccessFailed(res.get("errmsg"))
