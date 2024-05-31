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
from push import Telegram

key = {
    "token": "xxx",
    "chat_id": "xxx",
}

telegram = Telegram(key=key)

telegram.send("hello world.")
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

# 目前支持 pushplus, server, qmsg, workWechatRobot, workWechat, telegram
p = PushSender("qmsg", "21301137366cbdbabfc91e505cccb81e")

p.send("hello world")
```

## Parse

```python
from tools import parse

contents = [
    {
        "h1": {
            "content": "title 1",
            "style": "color: red",
            "newLine": "\n",
        },
        "h2": {
            "content": "title 2",
            "style": "color: red",
            "newLine": "\n",
        },
        "h3": {
            "content": "title 3",
            "style": "color: red",
            "newLine": "\n",
        },
        "h4": {
            "content": "title 4",
            "style": "color: red",
            "newLine": "\n",
        },
        "h5": {
            "content": "title 5",
            "newLine": "\n",
        },
        "h6": {
            "content": "title 6",
            "newLine": "\n",
        },
    },
    {
        "txt": {
            "content": "txt",
            "style": "font-size: 10px",
        },
        "code": {
            "content": "print('hello')",
        },
        "taskList": {
            "contents": [
                {
                    "content": "run 100 kilometers",
                    "style": "color: red",
                },
                {
                    "content": "do homeworks",
                    "complete": True,
                },
            ]
        },
        "blockQuote": {
            "content": "666",
            "style": "color: blue",
        },
        "strikethrough": {
            "content": "yeah",
            "style": "color: yello",
        },
        "italic": {
            "content": "yeah",
            "style": "color: yello",
        },
        "bold": {
            "content": "yeah",
            "style": "color: green",
        },
    },
    {
        "table": {
            "contents": [
                ("描述", "内容"),
                ("1", "A"),
            ],
        },
    },
    {
        "link": {
            "url": "https://xxx",
            "content": "hello",
            "style": "color: red",
        },
    },
    {
        "link": {
            "url": "https://yyy",
            "newLine": "++++\n",
        },
    },
    {
        "img": {
            "url": "https://abc.png",
            "alt": "abc",
        }
    },
]

print(parse(contents, template="html"))

print(parse(contents, template="txt"))

"""
title 1
title 2
title 3
title 4
title 5
title 6
txt
print('hello')
- [ ] run 100 kilometers
- [x] do homeworks
666
yeahyeahyeah
描述    内容
1       A

hello: https://xxx
link: https://yyy++++
abc: https://abc.png
"""

print(parse(contents))

"""
# title 1
## title 2
### title 3
#### title 4
##### title 5
###### title 6
txt
`print('hello')`
- [ ] run 100 kilometers
- [x] do homeworks
> 666
~~yeah~~*yeah***yeah**
|描述|内容|
|:--:|:--:|
|1|A|

[hello](https://xxx)
[link](https://yyy)++++
![abc](https://abc.png)
"""
```
