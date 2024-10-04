from push_tools import (
    push_composite,
    push_creator,
    server,
    pushplus,
    qmsg,
    workWechatRobot,
)

p = push_composite()
p.add("pushplus", pushplus("069ac..."))
p.add("qmsg", qmsg("5004..."))
p.add("server", server("SCT8..."))

p.send("hello world!", title="test")


w = push_creator(
    "workWechat",
    {
        "corpSecret": "slFn...",
        "corpid": "ww9f...",
    },
)

w.send("#title\nhello world!", agentid=1000002, msgtype="markdown")

w = workWechatRobot("ea3f7ac4..")

w.send("#title\nhello world!", msgtype="markdown")
