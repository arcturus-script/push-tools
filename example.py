"""Usage examples and offline smoke tests for push-tools.

This file doubles as documentation and as a runnable smoke test:

1. The *offline* cases (custom plugin + composite fan-out) run on every
   execution with no credentials and no network access.
2. The *real-service* cases are skipped while their credentials below are
   empty; fill the tokens in and run again to exercise the live APIs.

Run it with::

    python example.py

Third-party plugin packages are discovered automatically through the
``push_tools.channels`` entry-point group, e.g. in ``pyproject.toml``::

    [project.entry-points."push_tools.channels"]
    dingtalk = "push_dingtalk:DingTalkChannel"
"""

from __future__ import annotations

import logging

from push_tools import (
    PushChannel,
    PushComposite,
    PushPlus,
    PushResult,
    Qmsg,
    ServerChan,
    Telegram,
    WorkWechat,
    WorkWechatRobot,
    create_channel,
    load_plugins,
    push_composite,
    push_creator,
    push_server,
    register_channel,
    registry,
)
from push_tools.channels.qmsg import (
    STATUS_LABELS,
    STATUS_SENT,
    QmsgStatus,
)

# ====================================================================== #
# Credentials - leave them empty; fill in real values before live testing.
# ====================================================================== #
PUSHPLUS_TOKEN = ""
QMSG_KEY = ""
# Optional: a QQ group added and bound in the Qmsg console. Empty string
# means "push to the QQ single chat bound to the API key".
QMSG_GROUP = ""
SERVERCHAN_KEY = ""

# WeCom internal application credential (https://work.weixin.qq.com/).
WECHAT_CORP_ID = ""
WECHAT_CORP_SECRET = ""
WECHAT_AGENT_ID = 0
# Optional receiver userids, pipe-separated, e.g. "zhangsan|lisi". They MUST
# exist and stay inside the application's visible scope, otherwise the API
# returns errcode 81013 ("user & party & tag all invalid"). Empty = @all.
WECHAT_TOUSER = ""

# WeCom group robot webhook key.
WECHAT_ROBOT_KEY = ""

# Telegram bot credential (https://core.telegram.org/bots/api#sendmessage).
# The token is issued by @BotFather; the chat_id is a numeric id (read it from
# @userinfobot or the getUpdates API after messaging the bot once) or an
# "@channelusername" for a public channel the bot administers.
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""


# ====================================================================== #
# Custom plugin: an in-memory channel used for the offline test cases.
# ====================================================================== #
@register_channel("echo")
class EchoChannel(PushChannel):
    """Offline-only channel that pretends the message was delivered.

    Demonstrates the plugin contract: subclass :class:`PushChannel`,
    implement :meth:`send`, return ``self._succeed(...)``.

    Example:
        >>> EchoChannel().send("hello", title="ignored")   # doctest: +SKIP
    """

    def send(self, message, **options):
        # Record the call so the composite test can assert what was delivered.
        return self._succeed(raw={"message": message, "options": options})


# ====================================================================== #
# Offline case 1: registry / decorator / factory
# ====================================================================== #
def example_registry_and_factory() -> None:
    """Register a plugin, list channels, and build it through the factory.

    Example:
        >>> example_registry_and_factory()   # doctest: +SKIP
    """

    # Discover channels contributed by installed third-party packages.
    load_plugins()
    print("registered channels:", registry.names())

    # The decorator registered EchoChannel under the explicit name "echo".
    assert registry.is_registered("echo"), "echo plugin should be registered"

    # Factory lookup works for built-ins and plugins alike.
    pusher = create_channel("echo")
    assert isinstance(pusher, EchoChannel)

    result = pusher.send("hello from factory", title="greeting")
    assert isinstance(result, PushResult)
    assert result.success is True
    assert result.channel == "echo"
    assert result.raw["message"] == "hello from factory"
    print("factory result:", result)


# ====================================================================== #
# Offline case 2: composite fan-out
# ====================================================================== #
def example_composite() -> None:
    """Fan one message out to several children and collect results.

    Example:
        >>> example_composite()   # doctest: +SKIP
    """

    # Constructor accepts (name, channel) pairs; add() is chainable.
    group = PushComposite(
        [
            ("echo-1", create_channel("echo")),
            ("echo-2", EchoChannel()),
        ]
    ).add("echo-3", EchoChannel())

    assert group.names() == ["echo-1", "echo-2", "echo-3"]
    assert len(group) == 3 and "echo-1" in group

    # One call fans out; per-channel options (title/qq) are carried together
    # and each channel ignores the keys it does not understand.
    results = group.send("hello everyone", title="greeting", qq="10001")
    assert set(results) == {"echo-1", "echo-2", "echo-3"}
    assert all(result and result.success for result in results.values())
    print("composite results:", results)

    # Removing a missing name is a safe no-op; removing an existing child
    # shrinks the group.
    group.remove("missing").remove("echo-3")
    assert group.names() == ["echo-1", "echo-2"]


# ====================================================================== #
# Offline case 3: backward-compatible 0.0.1 API
# ====================================================================== #
def example_legacy_api() -> None:
    """The original push_server / push_composite / push_creator API still works.

    Example:
        >>> example_legacy_api()   # doctest: +SKIP
    """

    # Legacy static-dict-like mapping is now a live registry view.
    assert "pushplus" in push_server
    assert push_server["qmsg"] is Qmsg

    # Legacy composite class name.
    legacy_group = push_composite()
    legacy_group.add("echo", EchoChannel())
    results = legacy_group.send("legacy composite")
    assert results["echo"].success

    # Legacy creator: unknown names print instead of raising.
    broken = push_creator("does-not-exist", "irrelevant")
    assert broken.send("ignored") is None

    # Legacy creator with a valid (offline) channel.
    creator = push_creator("echo", None)
    assert creator.send("legacy creator").success


# ====================================================================== #
# Offline case 4: Qmsg API v3 contract (validation + response parsing)
# ====================================================================== #
def example_qmsg_v3_contract() -> None:
    """Exercise Qmsg v3 URL layout, validation and parsing without network.

    Example:
        >>> example_qmsg_v3_contract()   # doctest: +SKIP
    """

    from push_tools.channels import qmsg as qmsg_module
    from push_tools.errors import AccessFailed

    qmsg = Qmsg("dummy-key")

    # All v3 endpoints embed the key in the path under the /v3 prefix.
    assert qmsg.send_url.endswith("/v3/send/dummy-key")
    assert qmsg.json_send_url.endswith("/v3/jsend/dummy-key")
    assert qmsg.status_url.endswith("/v3/msg/status/dummy-key")

    # Client-side content constraints: the decorator logs and returns None.
    assert qmsg.send("") is None
    assert qmsg.send("x" * (Qmsg.max_message_length + 1)) is None

    # A status query needs a message id from a previous send.
    assert qmsg.query_status() is None

    # Successful v3 send body: ``success`` is true and ``data`` is the id.
    result = qmsg._parse_send_response({"success": True, "code": 0, "message": "ok", "data": 42})
    assert result.success and qmsg.last_msg_id == 42

    # Failed v3 send body raises AccessFailed carrying the remote message.
    try:
        qmsg._parse_send_response({"success": False, "code": 500, "message": "rate limited", "data": None})
        raise AssertionError("expected AccessFailed")
    except AccessFailed:
        pass

    # Status parsing is verified through a stubbed HTTP layer.
    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    original_get = qmsg_module.requests.get
    qmsg_module.requests.get = lambda url, **kw: _FakeResponse({"success": True, "code": 0, "message": "ok", "data": STATUS_SENT})
    try:
        # No argument: reuse the message id cached by the previous send.
        snapshot = qmsg.query_status()
    finally:
        qmsg_module.requests.get = original_get

    assert isinstance(snapshot, QmsgStatus)
    assert snapshot.msg_id == 42
    assert snapshot.code == STATUS_SENT
    assert snapshot.label == "sent"
    assert set(STATUS_LABELS.values()) == {"pending", "sent", "violation", "failed"}


# ====================================================================== #
# Offline case 5: ServerChan contract (SCT/SC3 endpoints + validation)
# ====================================================================== #
def example_serverchan_contract() -> None:
    """Exercise ServerChan endpoint routing, validation and parsing offline.

    Example:
        >>> example_serverchan_contract()   # doctest: +SKIP
    """

    from push_tools.channels import serverchan as sc_module
    from push_tools.errors import AccessFailed

    # Turbo key -> sctapi host; SC3 key -> {uid}.push.ft07.com host.
    turbo = ServerChan("SCTdummy")
    assert turbo.kind == "sct"
    assert turbo.send_url == "https://sctapi.ftqq.com/SCTdummy.send"

    sc3 = ServerChan("sctp123tDummyKey")
    assert sc3.kind == "sc3"
    assert sc3.send_url == "https://123.push.ft07.com/send/sctp123tDummyKey.send"

    # A malformed sctp key is rejected while constructing the channel.
    try:
        ServerChan("sctp-bad")
        raise AssertionError("expected ValueError for malformed SC3 key")
    except ValueError:
        pass

    # Title constraints from the docs: non-empty, one line, <= 32 chars.
    assert sc3._validate_title("ok") == "ok"
    for bad_title in ("", "   ", "line1\nline2", "x" * 33):
        try:
            sc3._validate_title(bad_title)
            raise AssertionError(f"expected ValueError for title={bad_title!r}")
        except ValueError:
            pass

    # Stub the HTTP layer and verify the JSON request body.
    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    captured = {}

    def _fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _FakeResponse({"code": 0, "message": "", "data": {"pushid": 1}})

    original_post = sc_module.requests.post
    sc_module.requests.post = _fake_post
    try:
        # Default title is supplied for fan-out calls without an explicit one.
        result = sc3.send("### body\nhello")
        assert result.success
        assert captured["url"].endswith("/sctp123tDummyKey.send")
        assert captured["json"] == {
            "title": "push-tools notification",
            "desp": "### body\nhello",
        }
        assert captured["headers"]["Content-Type"] == "application/json;charset=utf-8"
        assert captured["timeout"] == ServerChan("x").timeout

        # Documented options are forwarded; unrelated ones are filtered out.
        sc3.send(
            "hello",
            title="alert",
            short="short text",
            tags="deploy",
            channel="9",
            openid="o1,o2",
            group="ignored-by-serverchan",
        )
        assert captured["json"] == {
            "title": "alert",
            "desp": "hello",
            "short": "short text",
            "tags": "deploy",
            "channel": "9",
            "openid": "o1,o2",
        }
    finally:
        sc_module.requests.post = original_post

    # Invalid titles are caught by the decorator and reported as None.
    assert sc3.send("body", title="two\nlines") is None
    assert sc3.send("body", title="x" * 33) is None

    # Modern failures carry ``message``; legacy payloads use ``info``.
    try:
        sc3._parse_response({"code": 40001, "message": "BAD_SENDKEY"})
        raise AssertionError("expected AccessFailed")
    except AccessFailed:
        pass
    try:
        sc3._parse_response({"code": 40001, "info": "legacy reason"})
        raise AssertionError("expected AccessFailed")
    except AccessFailed:
        pass


# ====================================================================== #
# Offline case 6: WeCom contract (internal application + group robot)
# ====================================================================== #
def example_wechat_contract() -> None:
    """Exercise both WeCom channels offline against a stubbed HTTP layer.

    Covers access-token caching + one-shot refresh retry, every documented
    application message body, all robot message types and the documented
    size/format validation.

    Example:
        >>> example_wechat_contract()   # doctest: +SKIP
    """

    import base64
    import hashlib

    from push_tools.channels import wechat as wx

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    # Scripted gettoken response and a queue of one-shot POST responses.
    state = {
        "get": {"errcode": 0, "errmsg": "ok", "access_token": "TOK", "expires_in": 7200},
        "post_queue": [],
    }
    calls = []

    def _fake_get(url, **kwargs):
        calls.append({"verb": "GET", "url": url, **kwargs})
        return _FakeResponse(state["get"])

    def _fake_post(url, **kwargs):
        if state["post_queue"]:
            payload = state["post_queue"].pop(0)
        elif url.endswith("/media/upload") or url.endswith("/webhook/upload_media"):
            payload = {"errcode": 0, "errmsg": "ok", "type": "file", "media_id": "FID"}
        else:
            payload = {"errcode": 0, "errmsg": "ok", "msgid": "m1"}
        calls.append({"verb": "POST", "url": url, **kwargs})
        return _FakeResponse(payload)

    original_get = wx.requests.get
    original_post = wx.requests.post
    wx.requests.get = _fake_get
    wx.requests.post = _fake_post
    try:
        # ---- internal application ------------------------------------- #
        app = WorkWechat({"corpid": "ww", "corpSecret": "sec"})
        for bad_credential in (None, "string", {}, {"corpid": "ww"}, {"corpSecret": "s"}):
            try:
                WorkWechat(bad_credential)
                raise AssertionError("expected ValueError for %r" % (bad_credential,))
            except ValueError:
                pass

        # First send fetches a token, then posts the default @all envelope.
        result = app.send("hello", agentid=7)
        assert result.success and result.raw["msgid"] == "m1"
        assert calls[0]["verb"] == "GET"
        assert calls[0]["params"] == {"corpid": "ww", "corpsecret": "sec"}
        assert calls[1]["params"] == {"access_token": "TOK"}
        assert calls[1]["json"] == {
            "msgtype": "text",
            "agentid": 7,
            "touser": "@all",
            "text": {"content": "hello"},
        }

        # Second send reuses the cached token (no extra gettoken call) and
        # markdown is auto-detected; unrelated fan-out keys are dropped.
        calls.clear()
        app.send(
            "# hi\nthere",
            agentid=7,
            touser="u1|u2",
            toparty="3",
            safe=1,
            enable_duplicate_check=1,
            duplicate_check_interval=600,
            title="ignored",
            qq="1",
        )
        assert [c["verb"] for c in calls] == ["POST"]
        envelope = calls[0]["json"]
        assert envelope["msgtype"] == "markdown"
        assert envelope["markdown"] == {"content": "# hi\nthere"}
        assert envelope["touser"] == "u1|u2"
        assert envelope["toparty"] == "3"
        assert "totag" not in envelope
        assert envelope["safe"] == 1
        assert envelope["enable_duplicate_check"] == 1
        assert envelope["duplicate_check_interval"] == 600
        assert "title" not in envelope and "qq" not in envelope

        # Overlong content is truncated with an in-body notice instead of
        # being rejected; every posted body stays within the 2048-byte limit
        # and multi-byte characters are never cut in the middle.
        overlong = app.send("x" * 2049, agentid=7)
        assert overlong is not None
        sent_text = calls[-1]["json"]["text"]["content"]
        assert len(sent_text.encode("utf-8")) <= 2048
        assert sent_text.startswith("x" * 100) and "[truncated" in sent_text

        overlong_md = app.send("# " + "z" * 2047, agentid=7)
        assert overlong_md is not None
        sent_md = calls[-1]["json"]["markdown"]["content"]
        assert len(sent_md.encode("utf-8")) <= 2048
        assert sent_md.startswith("# ") and "[truncated" in sent_md

        wide = app.send("中" * 2048, agentid=7)  # 6144 UTF-8 bytes
        assert wide is not None
        sent_wide = calls[-1]["json"]["text"]["content"]
        assert len(sent_wide.encode("utf-8")) <= 2048

        typed = app.send_text("q" * 3000, agentid=7)
        assert typed is not None
        assert len(calls[-1]["json"]["text"]["content"].encode("utf-8")) <= 2048

        # Validation failures are caught by the decorator (None, no POST).
        assert app.send("hi") is None  # missing agentid
        assert app.send("hi", agentid=7, duplicate_check_interval=99999) is None
        assert app.send("   ", agentid=7) is None
        assert app.send("hi", agentid=7, msgtype="image") is None

        # Typed builders produce the exact documented bodies.
        app.send_textcard("t", "d", "https://a", btntxt="更多", agentid=7)
        assert calls[-1]["json"]["textcard"] == {
            "title": "t",
            "description": "d",
            "url": "https://a",
            "btntxt": "更多",
        }
        assert app.send_textcard("t", "d", "https://a", btntxt="12345", agentid=7) is None

        app.send_news([{"title": "a", "url": "u"}], agentid=7)
        assert calls[-1]["json"]["news"] == {"articles": [{"title": "a", "url": "u"}]}
        assert app.send_news([], agentid=7) is None
        assert app.send_news([{"title": "a"}] * 9, agentid=7) is None
        assert app.send_news([{"title": "a"}], agentid=7) is None
        assert app.send_news([{"title": "a", "appid": "wx1"}], agentid=7) is not None

        app.send_media("MID", "image", agentid=7)
        assert calls[-1]["json"]["image"] == {"media_id": "MID"}
        app.send_media("MID", "video", title="v", description="d", agentid=7)
        assert calls[-1]["json"]["video"] == {
            "media_id": "MID",
            "title": "v",
            "description": "d",
        }
        assert app.send_media("MID", "mp4", agentid=7) is None
        assert app.send_media("", "image", agentid=7) is None

        app.send_template_card({"card_type": "text_notice"}, agentid=7)
        assert calls[-1]["json"]["template_card"] == {"card_type": "text_notice"}
        assert app.send_template_card({}, agentid=7) is None

        # Expired cached token: refresh once and retry the same envelope.
        state["post_queue"] = [
            {"errcode": 42001, "errmsg": "access_token expired"},
            {"errcode": 0, "errmsg": "ok", "msgid": "m2"},
        ]
        app._invalidate_token()
        calls.clear()
        retried = app.send("after refresh", agentid=7)
        assert retried.success and retried.raw["msgid"] == "m2"
        assert [c["verb"] for c in calls] == ["GET", "POST", "GET", "POST"]

        # A non-token errcode must not trigger a retry.
        state["post_queue"] = [{"errcode": 81013, "errmsg": "all receivers invalid"}]
        calls.clear()
        assert app.send("x", agentid=7) is None
        assert [c["verb"] for c in calls] == ["POST"]

        # A rejected gettoken call surfaces as None.
        state["get"] = {"errcode": 40001, "errmsg": "invalid corpid"}
        bad_app = WorkWechat({"corpid": "ww", "corpSecret": "bad"})
        assert bad_app.get_access_token() is None
        assert bad_app.send("x", agentid=7) is None
        state["get"] = {"errcode": 0, "access_token": "TOK", "expires_in": 7200}

        # Temporary-media upload uses the "media" multipart field and size caps.
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 32
        assert app.upload_media("image", png_bytes) == "FID"
        upload_call = calls[-1]
        assert upload_call["params"]["type"] == "image"
        assert "media" in upload_call["files"]
        assert app.upload_media("voice", b"x" * (2 * 1024 * 1024 + 1)) is None
        assert app.upload_media("video3d", png_bytes) is None

        # ---- group robot ---------------------------------------------- #
        try:
            WorkWechatRobot("")
            raise AssertionError("expected ValueError for empty robot key")
        except ValueError:
            pass
        robot = WorkWechatRobot("key-123")

        robot.send(
            "hi",
            mentioned_list="zhang|wang",
            mentioned_mobile_list=["13800001111"],
            title="ignored",
        )
        assert calls[-1]["json"] == {
            "msgtype": "text",
            "text": {
                "content": "hi",
                "mentioned_list": ["zhang", "wang"],
                "mentioned_mobile_list": ["13800001111"],
            },
        }
        robot.send("# title")
        assert calls[-1]["json"]["msgtype"] == "markdown"
        robot.send("| a | b |", msgtype="markdown_v2")
        assert calls[-1]["json"] == {
            "msgtype": "markdown_v2",
            "markdown_v2": {"content": "| a | b |"},
        }

        # Byte limits: text 2048, markdown / markdown_v2 4096.
        assert robot.send("x" * 2049) is None
        assert robot.send("# " + "y" * 4095) is None
        assert robot.send("x", msgtype="nope") is None

        # Image: base64 + md5 of the raw bytes; JPG/PNG only, <= 2MB.
        image = b"\x89PNG\r\n\x1a\n" + b"0" * 64
        robot.send_image(image)
        image_body = calls[-1]["json"]["image"]
        assert image_body["md5"] == hashlib.md5(image).hexdigest()
        assert image_body["base64"] == base64.b64encode(image).decode("ascii")
        assert robot.send_image(b"GIF89a" + b"0" * 10) is None
        assert robot.send_image(b"\x89PNG\r\n\x1a\n" + b"x" * (2 * 1024 * 1024)) is None

        robot.send_news([{"title": "t", "url": "u", "description": "d", "extra": 1}])
        assert calls[-1]["json"]["news"]["articles"] == [{"title": "t", "url": "u", "description": "d"}]
        assert robot.send_news([]) is None
        assert robot.send_news([{"title": "t"}] * 9) is None
        assert robot.send_news([{"url": "u"}]) is None

        robot.send_file("MID")
        assert calls[-1]["json"] == {"msgtype": "file", "file": {"media_id": "MID"}}
        robot.send_voice("VID")
        assert calls[-1]["json"] == {"msgtype": "voice", "voice": {"media_id": "VID"}}
        robot.send_template_card({"card_type": "text_notice"})
        assert calls[-1]["json"]["template_card"] == {"card_type": "text_notice"}
        assert robot.send_file("") is None

        media_id = robot.upload("file", b"hello world")
        assert media_id == "FID"
        robot_upload = calls[-1]
        assert robot_upload["params"] == {"key": "key-123", "type": "file"}
        assert "media" in robot_upload["files"]
        assert robot.upload("image", b"x") is None
        assert robot.upload("file", b"") is None

        # send_local_file() uploads first and posts the file message second.
        calls.clear()
        robot.send_local_file(b"abc")
        assert calls[0]["url"].endswith("/webhook/upload_media")
        assert calls[1]["json"]["file"]["media_id"] == "FID"

        state["post_queue"] = [{"errcode": 93000, "errmsg": "webhook not found"}]
        assert robot.send("hi") is None
    finally:
        wx.requests.get = original_get
        wx.requests.post = original_post


# ====================================================================== #
# Offline case 7: Telegram Bot API 10.3 sendMessage contract
# ====================================================================== #
def example_telegram_contract() -> None:
    """Exercise the Telegram channel offline against a stubbed HTTP layer.

    Covers the bot-token endpoint format, JSON body construction, the full
    documented sendMessage option set (and unknown-option filtering), the
    1-4096 character text limit, parse_mode/entities exclusivity and the
    ok/error_code response envelope including ResponseParameters hints.

    Example:
        >>> example_telegram_contract()   # doctest: +SKIP
    """

    from push_tools.channels import telegram as tg
    from push_tools.errors import AccessFailed

    # A valid token embeds into the method URL; obvious junk is rejected at
    # construction time (never at first send).
    token = "123456789:AAEhBOweikSd39EXAMPLETOKEN1234567890"
    pusher = Telegram(token, chat_id=987654321)
    assert pusher.send_url == f"https://api.telegram.org/bot{token}/sendMessage"
    assert pusher.default_chat_id == 987654321
    for bad_token in ("", "no-colon", "abc:not-a-token", "12:short-secret", None):
        try:
            Telegram(bad_token)
            raise AssertionError("expected ValueError for %r" % (bad_token,))
        except ValueError:
            pass

    captured = {}

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def _fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _FakeResponse({"ok": True, "result": {"message_id": 42, "chat": {"id": 987654321}}})

    original_post = tg.requests.post
    tg.requests.post = _fake_post
    try:
        # Default chat id from the constructor is used and the body is JSON.
        result = pusher.send("hello")
        assert result.success and result.raw["result"]["message_id"] == 42
        assert captured["url"].endswith("/sendMessage")
        assert captured["json"] == {"chat_id": 987654321, "text": "hello"}
        assert captured["timeout"] == pusher.timeout

        # Per-send chat_id (numeric and @username) overrides the default.
        pusher.send("to group", chat_id=-1001234567890)
        assert captured["json"]["chat_id"] == -1001234567890
        pusher.send("to channel", chat_id="@my_channel")
        assert captured["json"]["chat_id"] == "@my_channel"

        # Every documented option is forwarded; None values and unrelated
        # fan-out keys (title/group/...) are filtered out.
        options = {
            "business_connection_id": "biz-1",
            "message_thread_id": 7,
            "direct_messages_topic_id": 9,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True, "url": "https://x"},
            "disable_notification": True,
            "protect_content": False,
            "allow_paid_broadcast": True,
            "message_effect_id": "eff-1",
            "ephemeral_message_parameters": {"receiver_user_id": 55},
            "suggested_post_parameters": {},
            "reply_parameters": {"message_id": 40},
            "reply_markup": {"inline_keyboard": []},
            "entities": None,
            "title": "ignored",
            "group": "ignored",
        }
        pusher.send("with options", **options)
        body = captured["json"]
        assert body["chat_id"] == 987654321 and body["text"] == "with options"
        for key in (
            "business_connection_id",
            "message_thread_id",
            "direct_messages_topic_id",
            "parse_mode",
            "link_preview_options",
            "disable_notification",
            "protect_content",
            "allow_paid_broadcast",
            "message_effect_id",
            "ephemeral_message_parameters",
            "suggested_post_parameters",
            "reply_parameters",
            "reply_markup",
        ):
            assert key in body, key
        assert "entities" not in body
        assert "title" not in body and "group" not in body

        # Validation failures are caught by the decorator -> None, no POST.
        # A channel without a default chat id requires one per send.
        no_chat = Telegram(token)
        before = len(captured)
        assert no_chat.send("x") is None
        assert no_chat.send("x", chat_id="   ") is None
        assert pusher.send("") is None
        assert pusher.send("   ") is None
        assert pusher.send("x" * 4097) is None
        assert pusher.send("x", parse_mode="BBCode") is None
        assert pusher.send("x", parse_mode="HTML", entities=[{"type": "bold"}]) is None
        assert len(captured) == before  # nothing was sent

        # Exactly 4096 characters is accepted; the 4097th is not.
        pusher.send("x" * 4096)
        assert captured["json"]["text"] == "x" * 4096

        # entities without parse_mode is a valid alternative.
        pusher.send("bold text", entities=[{"type": "bold", "offset": 0, "length": 4}])
        assert captured["json"]["entities"] == [{"type": "bold", "offset": 0, "length": 4}]
        assert "parse_mode" not in captured["json"]

        # Error envelopes: generic failure, flood control and group migration.
        def _fail(_url, **_kwargs):
            return _FakeResponse(_fail.payload)

        tg.requests.post = _fail
        _fail.payload = {"ok": False, "error_code": 401, "description": "Unauthorized"}
        assert pusher.send("x") is None
        try:
            pusher._parse_response(_fail.payload)
            raise AssertionError("expected AccessFailed")
        except AccessFailed as exc:
            assert "401" in str(exc) and "Unauthorized" in str(exc)

        _fail.payload = {
            "ok": False,
            "error_code": 429,
            "description": "Too Many Requests: retry after 15",
            "parameters": {"retry_after": 15},
        }
        try:
            pusher._parse_response(_fail.payload)
            raise AssertionError("expected AccessFailed")
        except AccessFailed as exc:
            assert "retry after 15s" in str(exc)

        _fail.payload = {
            "ok": False,
            "error_code": 403,
            "description": "group chat was upgraded to a supergroup",
            "parameters": {"migrate_to_chat_id": -1009876543210},
        }
        try:
            pusher._parse_response(_fail.payload)
            raise AssertionError("expected AccessFailed")
        except AccessFailed as exc:
            assert "-1009876543210" in str(exc)

        # An envelope missing ok=true is a failure even without error_code.
        try:
            pusher._parse_response({"ok": False, "description": "weird"})
            raise AssertionError("expected AccessFailed")
        except AccessFailed:
            pass

        tg.requests.post = _fake_post
    finally:
        tg.requests.post = original_post


# ====================================================================== #
# Offline case 8: PushPlus API V1.18 contract
# ====================================================================== #
def example_pushplus_contract() -> None:
    """Exercise the PushPlus channel offline against a stubbed HTTP layer.

    Covers the JSON body contract (token/content/template defaults, the
    leading-``#`` markdown auto-selection, every documented field and
    unknown-option filtering), the deprecated ``webhook`` -> ``option``
    alias, enum validation, the topic/to exclusivity rule, pushId
    requirements, integer timestamps, ``/batchSend`` channel/option
    alignment and the asynchronous code/msg response envelope.

    Example:
        >>> example_pushplus_contract()   # doctest: +SKIP
    """

    from push_tools.channels import pushplus as pp
    from push_tools.errors import AccessFailed

    # An empty/whitespace token is rejected at construction time.
    for bad_token in ("", "   ", None):
        try:
            PushPlus(bad_token)
            raise AssertionError("expected ValueError for %r" % (bad_token,))
        except ValueError:
            pass

    pusher = PushPlus("test-pushplus-token", timeout=7)
    captured = {}

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def _fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _FakeResponse(
            {"code": 200, "msg": "请求成功", "data": "short-code-123"}
        )

    original_post = pp.requests.post
    pp.requests.post = _fake_post
    try:
        # Minimal body: token + content + server-default html template.
        result = pusher.send("hello world.")
        assert result.success and result.raw["data"] == "short-code-123"
        assert captured["url"] == "https://www.pushplus.plus/send"
        assert captured["timeout"] == 7
        assert captured["json"] == {
            "token": "test-pushplus-token",
            "content": "hello world.",
            "template": "html",
        }

        # A leading Markdown heading auto-selects the markdown template.
        pusher.send("  # title\nbody", title="t")
        assert captured["json"]["template"] == "markdown"
        assert captured["json"]["title"] == "t"

        # Explicit template wins; all documented fields pass through while
        # unrelated fan-out keys (qq/group) and None values are dropped.
        pusher.send(
            "body",
            title="t",
            template="txt",
            channel="webhook",
            option="my-webhook-code",
            topic="ops",
            callbackUrl="https://cb.example/hook",
            timestamp=1632993318000,
            pre="appendMsg",
            pushId=None,
            qq="ignored",
            group="ignored",
        )
        body = captured["json"]
        assert body["template"] == "txt"
        assert body["channel"] == "webhook"
        assert body["option"] == "my-webhook-code"
        assert body["topic"] == "ops"
        assert body["callbackUrl"] == "https://cb.example/hook"
        assert body["timestamp"] == 1632993318000
        assert body["pre"] == "appendMsg"
        assert "pushId" not in body and "qq" not in body and "group" not in body

        # Deprecated alias: webhook=... is mapped to option=... only.
        pusher.send("body", webhook="legacy-code")
        assert captured["json"]["option"] == "legacy-code"
        assert "webhook" not in captured["json"]
        # Explicit option= wins over the legacy alias.
        pusher.send("body", option="new-code", webhook="legacy-code")
        assert captured["json"]["option"] == "new-code"

        # Validation failures -> None, no HTTP request made.
        before = len(captured)
        assert pusher.send("") is None
        assert pusher.send("   ") is None
        assert pusher.send("x", template="bbcode") is None
        assert pusher.send("x", channel="carrier-pigeon") is None
        assert pusher.send("x", topic="g", to="friend-token") is None
        assert pusher.send("x", template="form") is None
        assert pusher.send("x", template="doc") is None
        assert pusher.send("x", template="excel") is None
        assert pusher.send("x", timestamp=1632993318) is None  # seconds, not ms
        assert pusher.send("x", timestamp="1632993318000") is None  # must be int
        assert len(captured) == before

        # pushId satisfies form/doc/excel templates.
        for tpl in ("form", "doc", "excel"):
            pusher.send("body", template=tpl, pushId="obj-code-1")
            assert captured["json"]["template"] == tpl
            assert captured["json"]["pushId"] == "obj-code-1"

        # to without topic is valid (friend/business messages).
        pusher.send("body", to="token1,token2")
        assert captured["json"]["to"] == "token1,token2"

        # Error envelopes: documented codes with/without msg.
        def _fail(_url, **_kwargs):
            return _FakeResponse(_fail.payload)

        pp.requests.post = _fail
        _fail.payload = {"code": 903, "msg": "用户令牌不正确", "data": None}
        assert pusher.send("x") is None
        try:
            pusher._parse_response(_fail.payload)
            raise AssertionError("expected AccessFailed")
        except AccessFailed as exc:
            assert "903" in str(exc)
        # Missing msg falls back to the documented code meaning.
        try:
            pusher._parse_response({"code": 900})
            raise AssertionError("expected AccessFailed")
        except AccessFailed as exc:
            assert "900" in str(exc) and "restricted" in str(exc)
        try:
            pusher._parse_response({"code": 999, "msg": "bad title"})
            raise AssertionError("expected AccessFailed")
        except AccessFailed as exc:
            assert "bad title" in str(exc)

        # batchSend: parallel channel/option alignment, string and list forms.
        pp.requests.post = _fake_post
        result = pusher.batch_send(
            "deploy finished",
            ["wechat", "webhook", "mail"],
            options=[None, "my-webhook-code", "163"],
            title="alert",
        )
        assert result.success
        assert captured["url"] == "https://www.pushplus.plus/batchSend"
        body = captured["json"]
        assert body["channel"] == "wechat,webhook,mail"
        assert body["option"] == ",my-webhook-code,163"
        assert body["content"] == "deploy finished"
        assert body["title"] == "alert"
        assert body["template"] == "html"

        pusher.batch_send("x", "wechat,mail", options="cfg1,cfg2")
        assert captured["json"]["channel"] == "wechat,mail"
        assert captured["json"]["option"] == "cfg1,cfg2"

        # batchSend validation failures.
        assert pusher.batch_send("x", []) is None
        assert pusher.batch_send("x", ["wechat", "pigeon"]) is None
        assert pusher.batch_send("x", ["wechat", "mail"], options=["only-one"]) is None
        assert pusher.batch_send("", ["wechat"]) is None

        # batchSend response is a per-channel list envelope.
        pp.requests.post = _fail
        _fail.payload = {
            "code": 200,
            "msg": "执行成功",
            "data": [
                {"shortCode": "aaa", "code": 200, "channel": "wechat"},
                {"shortCode": "bbb", "code": 200, "channel": "mail"},
            ],
        }
        result = pusher.batch_send("x", ["wechat", "mail"])
        assert result.success and len(result.raw["data"]) == 2

        pp.requests.post = _fake_post
    finally:
        pp.requests.post = original_post


# ====================================================================== #
# Real-service cases - skipped while the credentials are empty.
# Fill the tokens above, then these functions send live messages.
# ====================================================================== #
def example_pushplus() -> None:
    """Send via PushPlus (API V1.18).

    Website: https://www.pushplus.plus  Docs: https://www.pushplus.plus/doc/

    Note:
        The API is asynchronous: a code-200 response only means the request
        was accepted; ``result.raw["data"]`` is the shortCode used to query
        the final delivery state (or set ``callbackUrl``). Real-name accounts
        are limited to 5 requests/minute and 200 wechat messages/day.

    Example:
        >>> example_pushplus()   # doctest: +SKIP
    """

    pusher = PushPlus(PUSHPLUS_TOKEN)

    # HTML is the default template; a leading "#" auto-selects markdown.
    accepted = pusher.send("hello world.", title="test")
    short_code = accepted.raw["data"]  # serial number, not a delivery receipt

    # Deliver to a group topic, or to friend tokens (the two are exclusive):
    #
    # pusher.send("# deploy\n- step 1\n- step 2",
    #             title="deploy", template="markdown", topic="ops-group")
    # pusher.send("for friends", to="friend-token-1,friend-token-2")

    # Forward to a webhook robot (WeCom/DingTalk/Feishu/...) whose config
    # code was created in the PushPlus console:
    #
    # pusher.send("build ok", title="ci", channel="webhook",
    #             option="my-dingtalk-code")

    # One request fanned out to several channels at once (/batchSend):
    #
    # pusher.batch_send("disk 92%", ["wechat", "webhook", "mail"],
    #                   options=[None, "my-dingtalk-code", "163"],
    #                   title="alert")
    _ = short_code


def example_qmsg() -> None:
    """Send via Qmsg API v3 and poll the delivery status.

    Website: https://qmsg.zendee.cn  Docs: https://qmsg.zendee.cn/docs

    Note:
        The API rate-limits each key to one submission every 5 seconds, so
        this example only performs a single send.

    Example:
        >>> example_qmsg()   # doctest: +SKIP
    """

    pusher = Qmsg(QMSG_KEY)

    # Default delivery target: the QQ single chat bound to the API key.
    result = pusher.send("hello world.")

    # Optional: deliver to a QQ group that was added and bound in the console.
    if QMSG_GROUP and result:
        pusher.send("hello group.", group=QMSG_GROUP)

    # The JSON endpoint /v3/jsend/{key} is an equivalent alternative:
    #
    # pusher.send_json("hello world.")

    # Pushing is asynchronous; poll the status with the returned message id.
    if result is not None:
        snapshot = pusher.query_status(result.raw["data"])
        print("qmsg delivery status:", snapshot)


def example_serverchan() -> None:
    """Send via ServerChan (Turbo SCT or SC3, auto-detected).

    Website: https://sct.ftqq.com  Docs: https://sct.ftqq.com/docs/

    The endpoint is chosen from the SendKey prefix: ``SCT...`` uses
    sctapi.ftqq.com, ``sctp{uid}t...`` uses {uid}.push.ft07.com.

    Example:
        >>> example_serverchan()   # doctest: +SKIP
    """

    pusher = ServerChan(SERVERCHAN_KEY)
    print("serverchan endpoint kind:", pusher.kind)

    # title is required by the API (<= 32 characters, one line); desp is a
    # Markdown body.
    pusher.send("### title\nhello world.", title="daily report")

    # Optional documented fields (uncomment as needed):
    #
    # pusher.send("disk usage 92%",
    #             title="alert",
    #             short="disk 92%",      # short notification text
    #             tags="ops",            # SC3 App tag grouping
    #             channel="9",           # console-defined channel number
    #             openid="o1,o2")        # cc recipients (subscriber feature)


def example_work_wechat() -> None:
    """Send messages via a WeCom internal application.

    Docs: https://developer.work.weixin.qq.com/document/path/90236
    (calling guide: https://developer.work.weixin.qq.com/document/path/90664)

    Example:
        >>> example_work_wechat()   # doctest: +SKIP
    """

    pusher = WorkWechat(
        {
            "corpid": WECHAT_CORP_ID,
            "corpSecret": WECHAT_CORP_SECRET,
        }
    )

    # A leading "#" auto-selects markdown; no receiver means touser="@all".
    pusher.send("# title\nhello world!", agentid=WECHAT_AGENT_ID)

    # Plain text with the documented envelope flags. Fill WECHAT_TOUSER with
    # real userids in the application's visible scope to target members; the
    # default @all avoids errcode 81013 from placeholder ids.
    pusher.send_text(
        "deploy finished",
        agentid=WECHAT_AGENT_ID,
        touser=WECHAT_TOUSER or "@all",
        safe=0,
        enable_duplicate_check=1,
        duplicate_check_interval=1800,
    )

    # Other documented types (uncomment as needed):
    #
    # pusher.send_textcard("领奖通知", "请于周五前领取",
    #                      "https://example.com/prize", btntxt="更多",
    #                      agentid=WECHAT_AGENT_ID)
    # pusher.send_news([{"title": "weekly report",
    #                    "url": "https://example.com/r",
    #                    "picurl": "https://example.com/p.png"}],
    #                 agentid=WECHAT_AGENT_ID)
    # media_id = pusher.upload_media("file", "./report.zip")
    # pusher.send_media(media_id, "file", agentid=WECHAT_AGENT_ID)


def example_work_wechat_robot() -> None:
    """Send messages via a WeCom group robot webhook ("消息推送").

    Docs: https://developer.work.weixin.qq.com/document/path/91770
    Limit: at most 20 messages/minute per webhook.

    Example:
        >>> example_work_wechat_robot()   # doctest: +SKIP
    """

    robot = WorkWechatRobot(WECHAT_ROBOT_KEY)

    # A leading "#" auto-selects markdown; markdown_v2 supports tables etc.
    robot.send("# title\nhello world!")
    robot.send("| name | status |\n|---|---|\n| db | ok |", msgtype="markdown_v2")

    # Text message mentioning everyone (also via mobile numbers):
    robot.send("deploy finished <@zhangsan>", mentioned_list=["@all"])

    # Other documented types (uncomment as needed):
    #
    # robot.send_image("./chart.png")           # JPG/PNG, <= 2MB
    # robot.send_news([{"title": "report", "url": "https://example.com"}])
    # robot.send_local_file("./report.zip")     # upload + file message
    #
    # with open("./note.amr", "rb") as fp:
    #     voice_id = robot.upload("voice", fp)  # AMR, <= 2MB / 60s
    # robot.send_voice(voice_id)


def example_telegram() -> None:
    """Send messages through a Telegram bot (Bot API 10.3 ``sendMessage``).

    Docs: https://core.telegram.org/bots/api#sendmessage

    Prerequisites: create a bot with @BotFather, copy the token, then send
    the bot one message and read your numeric chat id from @userinfobot (or
    the ``getUpdates`` method). A bot cannot message a user who has never
    started a chat with it.

    Example:
        >>> example_telegram()   # doctest: +SKIP
    """

    # A default chat_id lets send() work without options, which also makes
    # the channel safe inside a composite fan-out.
    pusher = Telegram(TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID)

    # Plain text; HTML formatting with the link preview disabled.
    pusher.send("deploy finished")
    pusher.send(
        '<b>alert</b> disk usage 92% &mdash; <a href="https://example.com">details</a>',
        parse_mode="HTML",
        link_preview_options={"is_disabled": True},
        disable_notification=True,
    )

    # MarkdownV2: remember to escape punctuation with backslashes.
    #
    # pusher.send("status \\_v2\\_: *bold* text", parse_mode="MarkdownV2")
    #
    # Forum topic / inline keyboard / protected content:
    #
    # pusher.send("build ok",
    #             message_thread_id=42,
    #             protect_content=True,
    #             reply_markup={"inline_keyboard": [[
    #                 {"text": "open", "url": "https://example.com"}]]})


def example_live_composite() -> None:
    """Fan out to several real channels in a single send call.

    Channels ignore the options they do not support, so ``title`` reaches
    PushPlus/ServerChan while ``group`` reaches Qmsg.

    Example:
        >>> example_live_composite()   # doctest: +SKIP
    """

    group = PushComposite()
    group.add("pushplus", PushPlus(PUSHPLUS_TOKEN))
    group.add("qmsg", Qmsg(QMSG_KEY))
    group.add("server", ServerChan(SERVERCHAN_KEY))

    # Each channel picks the options it understands and ignores the others.
    options = {"title": "test"}
    if QMSG_GROUP:
        options["group"] = QMSG_GROUP

    results = group.send("hello world!", **options)
    for name, result in results.items():
        print(name, "->", "ok" if result and result.success else "failed")


def main() -> None:
    # Channels log at INFO; enable the package logger to observe delivery.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    print("=== offline: registry + factory ===")
    example_registry_and_factory()

    print("\n=== offline: composite fan-out ===")
    example_composite()

    print("\n=== offline: legacy 0.0.1 API ===")
    example_legacy_api()

    print("\n=== offline: Qmsg API v3 contract ===")
    example_qmsg_v3_contract()

    print("\n=== offline: ServerChan contract ===")
    example_serverchan_contract()

    print("\n=== offline: WeCom contract ===")
    example_wechat_contract()

    print("\n=== offline: Telegram contract ===")
    example_telegram_contract()

    print("\n=== offline: PushPlus contract ===")
    example_pushplus_contract()

    # Real services are only contacted once the matching token is filled in.
    print("\n=== live services (skipped while tokens are empty) ===")
    if PUSHPLUS_TOKEN:
        example_pushplus()
    if QMSG_KEY:
        example_qmsg()
    if SERVERCHAN_KEY:
        example_serverchan()
    if WECHAT_CORP_ID and WECHAT_CORP_SECRET and WECHAT_AGENT_ID:
        example_work_wechat()
    if WECHAT_ROBOT_KEY:
        example_work_wechat_robot()
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        example_telegram()
    if PUSHPLUS_TOKEN and QMSG_KEY and SERVERCHAN_KEY:
        example_live_composite()


if __name__ == "__main__":
    main()
