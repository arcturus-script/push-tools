from .decorator import catchException
from .push import Push
import requests as re


class WorkWechatApp(Push):
    """
    企业微信推送
    内部应用开发文档(https://work.weixin.qq.com/api/doc/90000/90135/90664)
    接口调试工具(https://open.work.weixin.qq.com/wwopen/devtool/interface/combine)
    相关参数获取方法(https://work.weixin.qq.com/api/doc/90000/90135/90665)
    """

    token = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"

    url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"

    def __init__(self, key: dict) -> None:
        super().__init__(key)

    def get_access_token(self) -> str or None:
        corpSecret = self.key.get("corpSecret")
        corid = self.key.get("corpid")

        params = {
            "corpid": corid,
            "corpsecret": corpSecret,
        }

        res = re.get(self.token, params).json()

        if res.get("errcode") == 0:
            return res.get("access_token")
        else:
            print(f"Get access token failed, because: {res.get('errmsg')}")

    @catchException
    def send(self, msg: str, **kwargs) -> None:
        msgtype = kwargs.get("msgtype", "text")
        title = kwargs.get("title", "No title")

        data = {
            "msgtype": msgtype,
            msgtype: {"content": f"{title}\n{msg}"},
            "touser": kwargs.get("touser", "@all"),
            "toparty": kwargs.get("toparty", ""),
            "totag": kwargs.get("totag", ""),
            "agentid": self.key.get("agentid"),
            "safe": kwargs.get("safe", 0),
            "enable_duplicate_check": kwargs.get("duplicate_check", 0),
            "duplicate_check_interval": kwargs.get("check_interval", 1800),
        }

        params = {"access_token": self.get_access_token()}

        res = re.post(self.url, params=params, json=data).json()

        errcode = res.get("errcode")

        if errcode == 0:
            print("[WorkWechatApp] Message sent successfully.")
        else:
            raise Exception(res.get("errmsg"))


class WorkWechatRobot(Push):
    """
    企业微信群聊机器人
    配置说明(https://work.weixin.qq.com/api/doc/90000/90136/91770)
    """

    url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"

    def __init__(self, key: str) -> None:
        super().__init__(key)

    @catchException
    def send(self, msg: str, **kwargs) -> None:
        msgtype = kwargs.get("msgtype", "text")
        title = kwargs.get("title", "No title")

        res = re.post(
            self.url,
            params={"key": self.key},
            json={
                "msgtype": msgtype,
                msgtype: {"content": f"{title}\n{msg}"},
            },
        ).json()

        errcode = res.get("errcode")

        if errcode == 0:
            self.success()
        else:
            raise Exception(res.get("errmsg"))
