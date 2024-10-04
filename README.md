# push-tools

A repository for message push (๑•̀ㅂ•́)و✧

## usage

```python
from push_tools import pushplus

p = pushplus("069ac...")
p.send("hello world.", title="test")
```

```python
from push_tools import qmsg

q = qmsg("5004...")
q.send("hello world.")
```

```python
from push_tools import server

s = server("SCT8...")
s.send("###title\nhello world.", title="title")
```

```python
from push_tools import workWechat

w = workWechat({
    "corpSecret": "slFn...",
    "corpid": "ww9f...",
})

w.send("###title3\nhello world.", msgtype="markdown")
```

```python
from push_tools import workWechatRobot

robot = workWechatRobot("ea3f7ac4..")
robot.send("###title3\nhello world.", msgtype="markdown")
```

```python
from push import push_composite, pushplus, qmsg

p = PushComposite()
p.add("pushplus", pushplus("069ac..."))
p.add("qmsg", qmsg("5004..."))

p.send("title\nhello world.", title="title")
```

```python
from push import push_creator

p = push_creator("qmsg", "2130...")
p.send("hello world")
```
