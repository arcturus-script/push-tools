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

```python
from push import PushComposite, Pushplus, Qmsg

pushplus = Pushplus(key="xxx")
qmsg = Qmsg(key="xxx")

p = PushComposite()

p.add("pushplus", pushplus)
p.add("qmsg", qmsg)

p.send("hello world. ╰(*°▽°*)╯", title="test")
```

```python
from push import PushSender

p = PushSender("qmsg", "21301137366cbdbabfc91e505cccb81e")

p.send("hello world")
```
