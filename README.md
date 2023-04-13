# push

A repository for message push (๑•̀ㅂ•́)و✧

## Usage

```python
from push import Pushplus

pushplus = Pushplus(key="xxx")

pushplus.send("hello world.", title="test")
```

```python
from push import Qmsg

qmsg = Qmsg(key="xxx")

qmsg.send("hello world.")
```

```python
from push import Server

server = Server(key="xxx")

server.send("hello world.", title="test")
```

```python
from push import WorkWechatApp

key = {
    "agentid": 1000002,
    "corpSecret": "xxx",
    "corpid": "xxx",
}

wechat = WorkWechatApp(key=key)

wechat.send("hello world.", msgtype="markdown", title="## test")
```

```python
from push import WorkWechatRobot

robot = WorkWechatRobot(key="xxx")

robot.send("hello world.", msgtype="markdown", title="## test")
```
