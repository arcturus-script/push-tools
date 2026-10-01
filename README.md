# push-tools

一个小巧、可插拔的 Python 消息推送工具库 (๑•̀ㅂ•́)و✧ , 纯 AI 重构

一套统一的接口，把消息推送到 PushPlus（微信公众号等）、Qmsg（QQ）、ServerChan（Server酱）、Telegram Bot、企业微信内部应用、企业微信群机器人等渠道；支持多渠道一次扇出、工厂注册、第三方插件扩展。

- **Python**：>= 3.9
- **依赖**：[`requests`](https://pypi.org/project/requests/)
- **许可证**：MIT
- **内置示例**：仓库根目录 [`example.py`](./example.py)（含全部渠道的离线契约测试与实时推送示例）

---

## 目录

- [一、安装](#一安装)
- [二、快速开始](#二快速开始)
- [三、核心概念](#三核心概念)
- [四、渠道总览](#四渠道总览)
- [五、渠道详细说明](#五渠道详细说明)
  - [5.1 PushPlus（pushplus）](#51-pushpluspushplus)
  - [5.2 Qmsg（qmsg）](#52-qmsgqmsg)
  - [5.3 ServerChan / Server酱（server）](#53-serverchan--server酱server)
  - [5.4 Telegram Bot（telegram）](#54-telegram-bottelegram)
  - [5.5 企业微信内部应用（workWechat）](#55-企业微信内部应用workwechat)
  - [5.6 企业微信群机器人（workWechatRobot）](#56-企业微信群机器人workwechatrobot)
- [六、多渠道组合推送 PushComposite](#六多渠道组合推送-pushcomposite)
- [七、工厂与注册表](#七工厂与注册表)
- [八、错误处理](#八错误处理)
- [九、自定义渠道（插件）](#九自定义渠道插件)
- [十、0.0.1 旧版 API 兼容](#十001-旧版-api-兼容)
- [十一、离线测试与实时验证](#十一离线测试与实时验证)

---

## 一、安装

使用 [PDM](https://pdm.fming.dev/)（仓库自带 `pyproject.toml`/`pdm.lock`）：

```bash
pdm install
```

或直接用 pip 安装到任意环境（唯一运行时依赖是 `requests`）：

```bash
pip install requests
# 然后把 push_tools/ 目录放到你的项目中，或：
pip install .
```

---

## 二、快速开始

```python
import logging
logging.basicConfig(level=logging.INFO)   # 渠道内部用 logging 打印成功/失败

from push_tools import PushPlus

pusher = PushPlus("你的-pushplus-token")
result = pusher.send("hello world.", title="greeting")
print(result.success)   # True
```

用注册名通过工厂创建：

```python
from push_tools import create_channel

pusher = create_channel("qmsg", "你的-qmsg-key", timeout=5)
pusher.send("hello world")
```

一次调用扇出到多个渠道（各渠道自动忽略自己不认识的参数）：

```python
from push_tools import PushComposite, PushPlus, Qmsg

group = PushComposite()
group.add("pushplus", PushPlus("token-a"))
group.add("qmsg", Qmsg("key-b"))

results = group.send("hello everyone", title="greeting", group="123456")
# results == {"pushplus": PushResult(...), "qmsg": PushResult(...)}
```

---

## 三、核心概念

### 3.1 PushChannel

所有渠道都继承自 `push_tools.base.PushChannel`，统一约定：

- **构造函数**：`Channel(token, *, timeout=None)`
  - `token`：凭证。大多数渠道是字符串 key；企业微信内部应用是 `{"corpid": ..., "corpSecret": ...}` 字典；Telegram 额外支持构造参数 `chat_id`。
  - `timeout`：单次 HTTP 请求超时秒数，默认 `10.0`。
- **发送方法**：`send(message: str, **options) -> PushResult | None`
  - `message`：消息正文（非空字符串，各渠道有长度限制）。
  - `**options`：渠道参数。每个渠道只接受白名单内的参数，**其余参数静默忽略**——这保证一次 `PushComposite.send(...)` 可以同时携带给不同渠道的参数。
  - 返回 `PushResult` 表示服务端受理成功；方法被 `@catch_exception` 装饰，发生参数错误或服务端失败时记录日志并**返回 `None`**（不抛异常）。
- **Markdown 自动识别**：PushPlus 在正文以 `#` 开头时自动选择 `markdown` 模板；企业微信内部应用与群机器人在正文以 `#` 开头时自动选择 `markdown` 消息类型（显式指定 `template`/`msgtype` 时以显式值为准）。ServerChan 的正文 `desp` 本身即按 Markdown 渲染，无需选择类型。

### 3.2 PushResult

`push_tools.base.PushResult` 是不可变 dataclass：

| 字段 | 类型 | 说明 |
|---|---|---|
| `success` | `bool` | 恒为 `True`（失败时方法返回 `None`） |
| `channel` | `str` | 渠道注册名（如 `"pushplus"`） |
| `raw` | `Any` | 服务端原始 JSON 响应，用于排查与取流水号/消息 id |
| `message` | `str` | 可选的人类可读备注 |

```python
result = pusher.send("hello")
result.success          # True
result.channel          # 'pushplus'
result.raw              # 服务端返回的完整 dict
```

---

## 四、渠道总览

| 注册名 | 类（推荐） | 小写别名 | 凭证 `token` | 服务 |
|---|---|---|---|---|
| `pushplus` | `PushPlus` | `pushplus` | 用户/消息 token | PushPlus 推送加 |
| `qmsg` | `Qmsg` | `qmsg` | API Key | Qmsg（QQ 消息） |
| `server` | `ServerChan` | `server` | `SCT...` 或 `sctp{uid}t...` SendKey | ServerChan（Server酱） |
| `telegram` | `Telegram` | `telegram` | Bot Token（`<bot_id>:<secret>`） | Telegram Bot API |
| `workWechat` | `WorkWechat` | `workWechat` | `{"corpid", "corpSecret"}` | 企业微信内部应用 |
| `workWechatRobot` | `WorkWechatRobot` | `workWechatRobot` | 群机器人 webhook key | 企业微信消息推送机器人 |

查看当前所有已注册渠道（含第三方插件）：

```python
from push_tools import registry
print(registry.names())
# ['pushplus', 'qmsg', 'server', 'telegram', 'workWechat', 'workWechatRobot']
```

---

## 五、渠道详细说明

### 5.1 PushPlus（pushplus）

- 官网：<https://www.pushplus.plus> ｜ 接口文档（V1.18）：<https://www.pushplus.plus/doc/guide/api.html>
- 端点：`POST https://www.pushplus.plus/send`（单渠道）、`POST https://www.pushplus.plus/batchSend`（多渠道）
- 接口为**异步**：`code == 200` 只代表服务端受理，`raw["data"]` 是消息流水号（shortCode），不代表已送达；可用 `callbackUrl` 接收结果或用流水号查询。

**构造**

```python
PushPlus(token, *, timeout=None)
```

**`send(message, **options)` 参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `message`（→ `content`） | `str` | 是 | 消息内容，非空 |
| `title` | `str` | 否 | 消息标题 |
| `template` | `str` | 否 | 模板，默认 `html`；正文以 `#` 开头且未指定时自动用 `markdown`。可选值见下表 |
| `channel` | `str` | 否 | 发送渠道，默认 `wechat`，可选值见下表 |
| `topic` | `str` | 否 | 群组编码（一对多）；**与 `to` 互斥** |
| `to` | `str` | 否 | 好友令牌/企业微信用户 id，逗号分隔（实名最多 10 人，会员 100 人）；**与 `topic` 互斥** |
| `option` | `str` | 否 | 渠道配置编码（webhook/cp/mail/qq 渠道需在控制台预先配置） |
| `callbackUrl` | `str` | 否 | 异步发送结果回调地址 |
| `timestamp` | `int` | 否 | 毫秒级过期时间戳（如 `1632993318000`），服务器时间超过它则丢弃；必须为 13 位毫秒 int |
| `pre` | `str` | 否 | 预处理编码（会员功能） |
| `pushId` | `str` | 条件必填 | `template` 为 `form`/`doc`/`excel` 时必填（表单/文档/表格编码） |
| `webhook` | `str` | 否 | **已废弃别名**，等价于 `option`；两者同传时 `option` 优先 |

`template` 枚举：`html`、`txt`、`json`、`markdown`、`cloudMonitor`、`jenkins`、`route`、`pay`、`form`、`doc`、`excel`

`channel` 枚举：`wechat`（微信公众号）、`app`、`extension`（插件）、`webhook`（企微/钉钉/飞书/Bark 等机器人）、`clawbot`、`cmcc`、`qq`、`cp`（企业微信应用）、`mail`、`sms`（收费）、`voice`（收费）

**额外方法：`batch_send(message, channels, *, options=None, **fields)`** —— 一次请求发往多个渠道（`/batchSend`）

| 参数 | 类型 | 说明 |
|---|---|---|
| `message` | `str` | 消息内容 |
| `channels` | `list/tuple/str` | 渠道列表 `["wechat", "webhook"]` 或逗号字符串 `"wechat,webhook"` |
| `options` | `list/tuple/str` | 与渠道一一对应的配置编码列表，`None` 渲染为空条目（如 `[None, "code1"]` → `",code1"`），长度必须与渠道数一致；也可直接传逗号字符串 |
| `**fields` | - | 其余同 `send()`：`title`/`template`/`topic`/`to`/`callbackUrl`/`timestamp`/`pre`/`pushId` |

**返回码**（`raw["code"]`，失败时 `AccessFailed` 信息中带码）：200 受理成功、302 未登录、401 未授权、403 IP 未授权、500 系统异常、600 数据异常、805 无权查看、888 积分不足、900 账号受限（应停止当天推送）、903 token 无效、905 未实名认证、999 校验错误。

**限流（实名用户）**：1 分钟 5 次、相同内容 1 小时 3 条、微信渠道 200 次/天；标题 ≤100 字、内容 ≤2 万字（会员额度更高）。

```python
from push_tools import PushPlus

pusher = PushPlus("token")
pusher.send("hello world.", title="test")
pusher.send("# deploy\n- step 1", topic="ops-group")          # 自动 markdown
pusher.send("build ok", channel="webhook", option="dd-code")  # 转发到钉钉机器人
pusher.batch_send("disk 92%", ["wechat", "webhook", "mail"],
                  options=[None, "dd-code", "163"], title="alert")
```

---

### 5.2 Qmsg（qmsg）

- 官网：<https://qmsg.zendee.cn> ｜ 文档：<https://qmsg.zendee.cn/docs>（API v3）
- 推送到与 key 绑定的 QQ 私聊，或预先在控制台绑定的 QQ 群。

**构造**

```python
Qmsg(token, *, timeout=None)
```

**`send(message, **options)` 参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `message`（→ `msg`） | `str` | 是 | 文本内容，非空，≤ **1800** 字符 |
| `group` | `str` | 否 | 已绑定的 QQ 群号；不传则发到 key 绑定的 QQ 私聊 |

**额外方法**

| 方法 | 说明 |
|---|---|
| `send_json(message, group=None)` | 与 `send` 等价，但以 `application/json` 请求 `/v3/jsend/{key}` |
| `query_status(msg_id=None)` | 查询异步投递状态，返回 `QmsgStatus(msg_id, code, label, raw)`；不传 id 时复用本实例最近一次成功发送的 id |

投递状态码：`0` 待发送（pending）、`1` 已发送（sent）、`2` 内容违规（violation）、`-1` 发送失败（failed）。成功发送的消息 id 在 `result.raw["data"]`。

**限流**：每个 key 5 秒 1 条（托管私有机器人 0.5 秒 1 条）；日额度 500 条（私有机器人 1000 条）。

```python
from push_tools import Qmsg
from push_tools.channels.qmsg import STATUS_SENT   # 也可直接判断 code == 1

q = Qmsg("你的-qmsg-key")
result = q.send("backup finished")
msg_id = result.raw["data"]

q.send("deploy finished", group="123456789")   # 发绑定群

snapshot = q.query_status(msg_id)
if snapshot.code == STATUS_SENT:
    print("delivered")
```

---

### 5.3 ServerChan / Server酱（server）

- 官网：<https://sct.ftqq.com> ｜ 文档：<https://sct.ftqq.com/docs/>
- 自动识别两种 SendKey 并选择端点（与官方 SDK 一致）：

| SendKey 形态 | 端点 | `pusher.kind` |
|---|---|---|
| `SCT...`（ServerChanTurbo） | `https://sctapi.ftqq.com/{key}.send` | `"sct"` |
| `sctp{uid}t...`（Server酱³） | `https://{uid}.push.ft07.com/send/{key}.send` | `"sc3"` |

畸形的 `sctp` key 在**构造时**即抛 `ValueError`。请求体为 JSON（`Content-Type: application/json;charset=utf-8`）。

**构造**

```python
ServerChan(token, *, timeout=None)
```

**`send(message, **options)` 参数**（`message` → JSON 字段 `desp`）

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `message`（→ `desp`） | `str` | 是 | Markdown 正文 |
| `title` | `str` | 否 | 标题，API 必填，库内默认 `"push-tools notification"`；单行无换行，≤ **32** 字符 |
| `short` | `str` | 否 | 短通知内容 |
| `tags` | `str` | 否 | SC3 App 分组标签 |
| `channel` | `str` | 否 | 单次指定控制台"消息通道"的通道编号 |
| `openid` | `str` | 否 | 测试号/企业微信应用通道的额外接收人 |

成功判定 `code == 0`；失败读取 `message`（旧版兼容 `info`）。

**限额**：免费版 5 条/天，全站 50 次/分钟，建议把批量通知合并为一条。

```python
from push_tools import ServerChan

s = ServerChan("SCT-your-turbo-key")     # 或 "sctp123tYourSc3Key"
s.send("### report\nhello world", title="daily report")
s.send("disk 92%", title="alert", channel="9", tags="ops")
```

---

### 5.4 Telegram Bot（telegram）

- 文档：<https://core.telegram.org/bots/api#sendmessage>（实现对齐 Bot API 10.3 参数表）
- 端点：`POST https://api.telegram.org/bot<token>/sendMessage`
- 前置条件：用 [@BotFather](https://t.me/BotFather) 创建机器人取得 token；用户先给机器人发一条消息，再用 [@userinfobot](https://t.me/userinfobot) 或 `getUpdates` 取得数字 chat_id。机器人无法主动给未对话过的用户发消息。

**构造**

```python
Telegram(token, *, timeout=None, chat_id=None)
```

| 构造参数 | 类型 | 说明 |
|---|---|---|
| `token` | `str` | BotFather 颁发的 `<bot_id>:<secret>`，构造时做形态校验 |
| `chat_id` | `int/str` | 默认接收者（数字 id 或 `"@channelusername"`）；之后 `send()` 可不传 |

**`send(message, **options)` 参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `message`（→ `text`） | `str` | 是 | 文本，1–**4096** 字符（entities 解析后） |
| `chat_id` | `int/str` | 是* | 目标 chat；构造时给过默认值则可省略 |
| `parse_mode` | `str` | 否 | `HTML` / `Markdown` / `MarkdownV2` 之一 |
| `entities` | `list[dict]` | 否 | MessageEntity 数组，与 `parse_mode` **互斥** |
| `link_preview_options` | `dict` | 否 | 链接预览控制：`is_disabled`/`url`/`prefer_small_media`/`prefer_large_media`/`show_above_text` |
| `disable_notification` | `bool` | 否 | 静默发送 |
| `protect_content` | `bool` | 否 | 禁止转发/保存 |
| `allow_paid_broadcast` | `bool` | 否 | 允许付费广播（最高 1000 条/秒，0.1 Stars/条） |
| `message_thread_id` | `int` | 否 | 论坛话题（topic）id |
| `direct_messages_topic_id` | `int` | 否 | 私信话题 id |
| `business_connection_id` | `str` | 否 | 商业连接 id |
| `message_effect_id` | `str` | 否 | 消息特效 id（仅私聊） |
| `ephemeral_message_parameters` | `dict` | 否 | 临时消息参数 |
| `suggested_post_parameters` | `dict` | 否 | 建议帖子参数 |
| `reply_parameters` | `dict` | 否 | 被回复消息描述 |
| `reply_markup` | `dict` | 否 | 内联键盘/自定义键盘/`ReplyKeyboardRemove`/`ForceReply` |

成功判定 `ok == true`，`raw` 为 Message 对象；失败信息含 `error_code` 与 `description`，429 附带 `retry_after` 秒数，群升级超组附带 `migrate_to_chat_id`。

**广播限额**：默认 30 条/秒。

```python
from push_tools import Telegram

bot = Telegram("123456789:AAEhBO...", chat_id=987654321)
bot.send("deploy finished")
bot.send('<b>alert</b> disk 92% <a href="https://x.com">details</a>',
         parse_mode="HTML",
         link_preview_options={"is_disabled": True},
         disable_notification=True)
bot.send("build ok", chat_id="@my_channel",
         message_thread_id=42,
         reply_markup={"inline_keyboard": [[
             {"text": "open", "url": "https://example.com"}]]})
```

---

### 5.5 企业微信内部应用（workWechat）

- 文档：调用指南 <https://developer.work.weixin.qq.com/document/path/90664> ｜ 应用消息 <https://developer.work.weixin.qq.com/document/path/90236> ｜ 临时素材 path/90253
- access_token 懒加载并缓存至到期前 5 分钟；发送时若 token 失效（errcode 40014/41001/42001）自动刷新并重试一次。

**构造**

```python
WorkWechat(token, *, timeout=None)
# token 必须是 {"corpid": "企业ID", "corpSecret": "应用Secret"}
```

**通用信封参数**（`send()` 及所有 `send_*` 方法的 `**options`）

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `agentid` | `int/str` | 是 | 应用 agentid（自建应用设置页可见） |
| `touser` | `str` | 否 | 成员 userid，`\|` 分隔；`touser/toparty/totag` 全空时默认 `@all` |
| `toparty` | `str` | 否 | 部门 id，`\|` 分隔 |
| `totag` | `str` | 否 | 标签 id，`\|` 分隔 |
| `safe` | `bool/int` | 否 | 是否保密消息（0/1） |
| `enable_id_trans` | `int` | 否 | 是否开启 id 转译 |
| `enable_duplicate_check` | `int` | 否 | 是否开启重复消息检查 |
| `duplicate_check_interval` | `int` | 否 | 重复检查间隔，0–14400 秒 |

> 接收人必须在应用**可见范围**内，否则返回 errcode 81013（user & party & tag all invalid）；部分无效时 errcode 仍为 0，但 `raw` 中带 `invaliduser` 等字段。

**消息方法**

| 方法 | 说明 | 约束 |
|---|---|---|
| `send(message, **opts)` | 发 text/markdown；以 `#` 开头自动 markdown，也可显式 `msgtype="markdown"` | ≤2048 UTF-8 字节 |
| `send_text(content, **opts)` | 文本（支持 `\n` 与 `<a>`） | ≤2048 字节 |
| `send_markdown(content, **opts)` | Markdown | ≤2048 字节 |
| `send_textcard(title, description, url, btntxt=None, **opts)` | 文本卡片 | title 必填；`btntxt` ≤4 字；`url` 需带 http(s) |
| `send_news(articles, **opts)` | 图文消息，1–8 条 | 每篇需 `title` 且需 `url` 或 `appid`(+`pagepath`)，可选 `description`/`picurl` |
| `send_media(media_id, msgtype="image", *, title=None, description=None, **opts)` | image/voice/video/file | `msgtype` ∈ `image/voice/video/file`；video 可用 `title`/`description` |
| `send_template_card(card, **opts)` | 模板卡片 | 传入完整 card dict，需含 `card_type` |
| `upload_media(media_type, file)` | 上传临时素材，返回 `media_id`（3 天有效） | image ≤10MB、voice(AMR) ≤2MB、video(MP4) ≤10MB、file ≤20MB；`file` 为路径或二进制文件对象 |
| `get_access_token()` | 取/刷新 access token | 一般无需手动调用 |
| `raw_send(body)` | 直接发送完整信封 | 用于 mpnews、miniprogram_notice、卡片回调等未封装类型 |

```python
from push_tools import WorkWechat

w = WorkWechat({"corpid": "ww9f...", "corpSecret": "slFn..."})

w.send("hello world", agentid=1000002)                      # 默认 @all
w.send("# title\nhello world", agentid=1000002)             # 自动 markdown
w.send_text("deploy finished", agentid=1000002,
            touser="zhangsan|lisi", enable_duplicate_check=1,
            duplicate_check_interval=1800)
w.send_textcard("领奖通知", "请于周五前领取",
                "https://example.com/prize", btntxt="更多", agentid=1000002)

media_id = w.upload_media("file", "./report.zip")
w.send_media(media_id, "file", agentid=1000002)
```

---

### 5.6 企业微信群机器人（workWechatRobot）

- 文档：<https://developer.work.weixin.qq.com/document/path/91770>
- `token` 是机器人 webhook URL 中的 `key` 参数。

**构造**

```python
WorkWechatRobot(token, *, timeout=None)
```

**`send(message, **options)` 参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `message` | `str` | 是 | 文本内容 |
| `msgtype` | `str` | 否 | `text` / `markdown` / `markdown_v2`；不传时以 `#` 开头自动选 `markdown`，否则 `text` |
| `mentioned_list` | `list/str` | 否 | 提醒成员 userid 列表（或 `\|` 分隔字符串），`["@all"]` 提醒所有人；仅 text 生效 |
| `mentioned_mobile_list` | `list/str` | 否 | 按手机号提醒，格式同上；仅 text 生效 |

正文内可用 `<@userid>` 语法 @ 人（markdown_v2 不支持 @）。

**类型方法与限额**

| 方法 | 说明 | 限额 |
|---|---|---|
| `send_text(content, mentioned_list=None, mentioned_mobile_list=None)` | 文本 | ≤2048 UTF-8 字节 |
| `send_markdown(content)` | Markdown | ≤4096 字节 |
| `send_markdown_v2(content)` | 新版 Markdown（表格/列表/嵌套引用），不支持颜色与 @ | ≤4096 字节 |
| `send_image(source)` | 图片，`source` 为路径/文件对象/bytes，自动 base64+md5 | 仅 JPG/PNG（魔数校验），≤2MB |
| `send_news(articles)` | 图文，1–8 条，每篇需 `title`+`url`，可选 `description`/`picurl` | ≤8 条 |
| `send_file(media_id)` | 文件消息 | media_id 来自 `upload` |
| `send_voice(media_id)` | 语音消息 | AMR |
| `send_template_card(card)` | 模板卡片（text_notice/news_notice） | 传入完整 dict |
| `upload(media_type, file)` | 上传素材返回 media_id（3 天有效，仅本机器人可用） | `file` ≤20MB；`voice`(AMR) ≤2MB；multipart 字段名为 `media` |
| `send_local_file(path)` | 上传本地文件并立即以 file 消息发出 | ≤20MB |
| `raw_send(body)` | 直接发送完整 JSON 信封 | - |

**频率**：每个 webhook 20 条/分钟。

```python
from push_tools import WorkWechatRobot

robot = WorkWechatRobot("webhook-key")
robot.send("# title\nhello world")
robot.send("deploy finished <@zhangsan>", mentioned_list=["@all"])
robot.send_image("./chart.png")
robot.send_local_file("./report.zip")
```

---

## 六、多渠道组合推送 PushComposite

`push_tools.PushComposite`（旧别名 `push_composite`）把多个渠道聚合为同一个 `send` 接口。**子渠道相互隔离**：任一渠道抛异常或返回 `None` 都不影响其余渠道。

**构造与管理**

```python
PushComposite(children=None, *, timeout=None)
```

| 成员 | 说明 |
|---|---|
| `add(name, channel)` | 添加子渠道；也支持 `add(channel)` 单参数形式（自动取注册名）；返回 `self` 可链式调用 |
| `remove(name)` | 移除子渠道（不存在时忽略）；返回 `self` |
| `get(name)` | 按名取子渠道 |
| `names()` | 按插入顺序返回子渠道名 |
| `__contains__` / `__iter__` / `__len__` | 支持 `name in group`、迭代、`len(group)` |

`children` 支持 `{name: channel}` 字典或 `[(name, channel), ...]` 列表。

**发送**：`send(message, **options) -> dict[str, PushResult | None]`，返回 `{子渠道名: 结果}`，值为 `None` 表示该渠道失败。

```python
from push_tools import PushComposite, PushPlus, Qmsg, ServerChan

group = PushComposite([
    ("pushplus", PushPlus("token-a")),
    ("qmsg", Qmsg("key-b")),
]).add("server", ServerChan("SCT-key-c"))

results = group.send("title\nhello world.",
                     title="title",      # -> PushPlus / ServerChan
                     group="123456")     # -> Qmsg；其它渠道自动忽略

for name, result in results.items():
    print(name, "ok" if result and result.success else "failed")
```

---

## 七、工厂与注册表

```python
from push_tools import create_channel, registry
```

- `create_channel(kind, token=None, *, timeout=None, **options) -> PushChannel`
  按注册名实例化渠道；`**options` 透传给渠道构造函数（如 Telegram 的 `chat_id`）。未知名称抛 `UnknownChannelError`。

  ```python
  pusher = create_channel("telegram", "123456789:AAEhBO...", chat_id=99, timeout=5)
  ```

- `registry.names()`：列出全部已注册渠道名。
- `load_plugins()`：发现并加载通过 entry point 安装的第三方渠道插件。

---

## 八、错误处理

内置渠道的发送方法都被 `@catch_exception` 装饰：

- 参数错误（`ValueError`）、服务端业务失败（`AccessFailed`）都会以 `ERROR` 级别写入名为 `push_tools` 的 logger，方法返回 `None`。
- 因此调用方有两种判断方式：

```python
# 方式一：判空（推荐用于扇出/批处理）
result = pusher.send("hello")
if result is None:
    ...  # 失败原因已写入日志

# 方式二：直接调用解析方法可拿到异常（不经过装饰器）
from push_tools.errors import AccessFailed
try:
    pusher._parse_response({"code": 903, "msg": "bad token"})
except AccessFailed as exc:
    print(exc)
```

开启日志查看详细原因：

```python
import logging
logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s %(name)s: %(message)s")
# INFO  push_tools: [pushplus] Operate successfully.
# ERROR push_tools: [Qmsg] An error occurred, because > AccessFailed: ...
```

异常层级（`push_tools.errors`）：`PushToolsError` → `PushChannelError` → `AccessFailed`；另有 `UnknownChannelError`、`ChannelAlreadyRegistered`。

---

## 九、自定义渠道（插件）

继承 `PushChannel` 并用 `@register_channel` 注册即可被工厂发现：

```python
from push_tools import PushChannel, register_channel, create_channel

@register_channel("stdout")
class StdoutChannel(PushChannel):
    allowed_options = frozenset({"prefix"})   # 声明本渠道接受的参数

    def send(self, message, **options):
        prefix = options.get("prefix", "")
        print(prefix, message)
        return self._succeed(raw={"echo": message})

create_channel("stdout").send("hello")
```

约定：

- 用 `self._succeed(raw=响应数据)` 记录成功日志并返回 `PushResult`；
- 用 `allowed_options` 类属性 + `self._filter_options(**options)` 做参数白名单，保证组合扇出安全；
- HTTP 调用用 `requests`、超时传 `self.timeout`；失败抛 `AccessFailed` 并加 `@catch_exception`；
- 第三方包还可通过 `push_tools.channels` entry point 分发渠道，无需改本仓库代码。

---

## 十、0.0.1 旧版 API 兼容

以下小写别名与旧入口保持可用，新代码建议使用 PEP-8 类名与 `create_channel`：

| 旧用法 | 等价新用法 |
|---|---|
| `pushplus(...)` / `from push_tools import pushplus` | `PushPlus(...)` |
| `qmsg(...)` | `Qmsg(...)` |
| `server(...)` | `ServerChan(...)` |
| `telegram(...)` | `Telegram(...)` |
| `workWechat({...})` | `WorkWechat({...})` |
| `workWechatRobot(...)` | `WorkWechatRobot(...)` |
| `push_composite` | `PushComposite` |
| `push_server`（字典） | `registry` / `push_server` 动态只读视图 |
| `push_creator("qmsg", key)` | `create_channel("qmsg", key)` |

`push_creator` 保留旧行为：未知类型只打印 `Unsupported push type: ...` 而不抛异常。

---

## 十一、离线测试与实时验证

仓库的 [`example.py`](./example.py) 包含：

- **离线契约用例**（不发真实网络请求，stub 掉 HTTP 层），覆盖全部渠道的请求体构造、参数校验、限额边界、错误响应解析：
  - `example_registry_and_factory()`、`example_composite()`、`example_legacy_api()`
  - `example_qmsg_v3_contract()`、`example_serverchan_contract()`、`example_wechat_contract()`
  - `example_telegram_contract()`、`example_pushplus_contract()`
- **实时用例**（`example_pushplus()` / `example_qmsg()` / `example_serverchan()` / `example_work_wechat()` / `example_work_wechat_robot()` / `example_telegram()` / `example_live_composite()`）：在文件顶部填入对应 token 后才会真实发送，凭证为空时自动跳过。

运行：

```bash
.venv/bin/python example.py            # 先跑全部离线用例，再对已填凭证的渠道实时推送

# 只跑某一个离线用例：
.venv/bin/python -c "import logging; logging.basicConfig(level=logging.CRITICAL); \
import example; example.example_pushplus_contract()"
```

---

### 官方文档链接汇总

| 渠道 | 文档 |
|---|---|
| PushPlus | <https://www.pushplus.plus/doc/> |
| Qmsg | <https://qmsg.zendee.cn/docs> |
| ServerChan | <https://sct.ftqq.com/docs/> |
| Telegram Bot API | <https://core.telegram.org/bots/api> |
| 企业微信内部应用 | <https://developer.work.weixin.qq.com/document/path/90236> |
| 企业微信群机器人 | <https://developer.work.weixin.qq.com/document/path/91770> |
