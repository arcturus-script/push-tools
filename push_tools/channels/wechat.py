"""WeCom (WeChat Work / 企业微信) push channels.

Two channels are provided:

- :class:`WorkWechat` - messages sent by an *internal application*
  (corpid + corpSecret). The overall calling rules (HTTPS, JSON, UTF-8,
  access-token caching, frequency limits, trusted IP) are described at
  https://developer.work.weixin.qq.com/document/path/90664 and the message
  types are defined at
  https://developer.work.weixin.qq.com/document/path/90236
  (``send`` / access token / temporary media upload).
- :class:`WorkWechatRobot` - messages sent by a *group robot webhook*
  ("消息推送", formerly 群机器人), documented at
  https://developer.work.weixin.qq.com/document/path/91770.

Common facts from the docs:

- Every response is JSON; success means ``errcode`` is missing or ``0`` and
  ``errmsg`` must never be used as the success criterion.
- The application channel needs an ``access_token`` (valid for 7200 seconds)
  which must be cached and re-fetched lazily; per-member limits are 30
  messages/minute and 1000 messages/hour.
- The robot webhook is limited to 20 messages/minute per webhook; uploaded
  ``media_id`` values are only valid for 3 days and only for the robot that
  uploaded them.
"""

from __future__ import annotations

import base64
import hashlib
import os
import time
from typing import Any, Optional

import requests

from ..base import PushChannel
from ..errors import AccessFailed, catch_exception
from ..registry import register_channel

# Refresh the cached access token this many seconds before its real expiry to
# absorb clock skew between the local machine and the WeCom servers.
_TOKEN_EXPIRY_MARGIN = 300

# errcode values that mean "the access token you used is missing/expired".
# On any of these the message is retried once with a force-refreshed token.
# 40014: invalid access_token, 41001: missing, 42001: expired.
_TOKEN_INVALID_ERRCODES = frozenset({40014, 41001, 42001})

_MB = 1024 * 1024

# Application text/markdown content limit (UTF-8 bytes, see path/90236).
_APP_CONTENT_MAX_BYTES = 2048

# Temporary-media size limits for the application channel (path/90253):
# image 10MB, voice 2MB (AMR, <= 60s), video 10MB, ordinary file 20MB.
_APP_MEDIA_MAX_BYTES = {
    "image": 10 * _MB,
    "voice": 2 * _MB,
    "video": 10 * _MB,
    "file": 20 * _MB,
}

# Application message types that only carry {"media_id": ...} (video also
# carries an optional title/description).
_MEDIA_MSGTYPES = frozenset({"image", "voice", "video", "file"})


def _check_errcode(data: dict) -> dict:
    """Return ``data`` when a WeCom response is successful.

    The docs are explicit: judge success from ``errcode`` (present and
    non-zero means failure), never from ``errmsg``.

    Raises:
        AccessFailed: With the server-provided ``errmsg`` on failure.
    """

    errcode = data.get("errcode")
    if errcode in (None, 0):
        return data
    raise AccessFailed(f"errcode {errcode}: {data.get('errmsg', '')}".rstrip(": "))


def _utf8_size(text: str) -> int:
    """Return the UTF-8 encoded byte length of ``text``."""

    return len(text.encode("utf-8"))


def _read_source(source: Any) -> "tuple[Optional[str], bytes]":
    """Normalize a file path, binary file object or ``bytes`` value.

    Returns:
        A ``(filename, raw_bytes)`` tuple; ``filename`` is ``None`` when the
        source was raw bytes or a file object without a ``name`` attribute.

    Raises:
        TypeError: When ``source`` is none of the supported types.
    """

    if isinstance(source, (str, os.PathLike)):
        path = os.fspath(source)
        with open(path, "rb") as fp:
            return os.path.basename(path), fp.read()
    if isinstance(source, bytes):
        return None, source
    if hasattr(source, "read"):
        name = getattr(source, "name", None)
        return (os.path.basename(name) if name else None), source.read()
    raise TypeError("source must be a file path, a binary file object or bytes")


def _as_member_list(value: Any) -> "Optional[list[str]]":
    """Normalize a robot mention field into a JSON array of strings.

    The robot API expects arrays (``["zhangsan", "@all"]``). A single string
    is accepted as a convenience and split on ``|`` like the application
    API's receiver fields.
    """

    if value is None:
        return None
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()] or None
    return [str(item) for item in value]


@register_channel("workWechat")
class WorkWechat(PushChannel):
    """Send messages through a WeCom internal application.

    The constructor credential is a dict::

        {"corpid": "<enterprise id>", "corpSecret": "<application secret>"}

    Every call needs ``agentid`` (the application agent id, shown on the
    application settings page); pass it once per send as ``agentid=...``.
    Receiver options ``touser`` / ``toparty`` / ``totag`` accept the
    pipe-separated id strings documented by the API; when none is given the
    message defaults to ``touser="@all"``.

    The access token is fetched lazily and cached until (almost) expiry, so
    sending many messages costs one ``gettoken`` request per 2 hours. If a
    cached token is rejected mid-life (errcode 40014/41001/42001), the send
    is automatically retried once with a freshly fetched token.

    Example:
        Text message to every member of the enterprise::

            pusher = WorkWechat({
                "corpid": "ww9f-your-corp-id",
                "corpSecret": "your-app-secret",
            })
            pusher.send("hello world", agentid=1000002)

        Markdown is auto-detected from a leading ``#``::

            pusher.send("# title\\nhello world", agentid=1000002)

        A text card with a click-through link::

            pusher.send_textcard("领奖通知", "请于周五前领取",
                                 "https://example.com/prize",
                                 btntxt="更多", agentid=1000002)
    """

    # Endpoint that exchanges corpid/corpSecret for an access token.
    token_url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    # Endpoint that sends an application message.
    send_url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
    # Endpoint that uploads temporary media (image/voice/video/file).
    media_upload_url = "https://qyapi.weixin.qq.com/cgi-bin/media/upload"

    # Keyword arguments allowed inside a message envelope; everything else
    # in a fan-out call (e.g. ``title=...``, ``qq=...``) is ignored.
    allowed_options = frozenset(
        {
            "agentid",
            "touser",
            "toparty",
            "totag",
            "safe",
            "enable_id_trans",
            "enable_duplicate_check",
            "duplicate_check_interval",
        }
    )

    def __init__(self, token=None, *, timeout=None):
        super().__init__(token, timeout=timeout)
        if not isinstance(token, dict):
            raise ValueError("WorkWechat token must be a {'corpid': ..., 'corpSecret': ...} dict")
        if not token.get("corpid") or not token.get("corpSecret"):
            raise ValueError("both 'corpid' and 'corpSecret' are required")
        # Cached access token + its local expiry timestamp (epoch seconds).
        self._access_token = None
        self._access_token_expires_at = 0.0

    @catch_exception
    def get_access_token(self):
        """Return a valid access token, fetching and caching it when needed.

        Tokens are valid for 7200 seconds per the docs and the gettoken
        endpoint itself is rate limited, so the cached value is reused until
        :data:`_TOKEN_EXPIRY_MARGIN` seconds before its real expiry.

        Returns:
            The token string on success; ``None`` (after logging) when the
            remote call fails.

        Example:
            >>> token = pusher.get_access_token()   # doctest: +SKIP
        """

        # Reuse the cached token while it is still safely valid.
        if self._access_token and time.time() < self._access_token_expires_at:
            return self._access_token

        params = {
            "corpid": self.token["corpid"],
            "corpsecret": self.token["corpSecret"],
        }
        data = requests.get(self.token_url, params=params, timeout=self.timeout).json()
        _check_errcode(data)

        self._access_token = data["access_token"]
        self._access_token_expires_at = time.time() + int(data.get("expires_in", 7200)) - _TOKEN_EXPIRY_MARGIN
        return self._access_token

    def _invalidate_token(self) -> None:
        """Drop the cached token so the next send fetches a new one."""

        self._access_token = None
        self._access_token_expires_at = 0.0

    @catch_exception
    def send(self, message, **options):
        """Send a plain-text or Markdown message.

        ``msgtype`` defaults to ``"text"``; pass ``msgtype="markdown"`` or
        start the message with a leading ``#`` to send Markdown (the
        application Markdown subset is documented at path/90236).

        Example:
            >>> pusher.send("hello", agentid=1000002, touser="zhangsan")
            ...                                              # doctest: +SKIP
        """

        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")
        if _utf8_size(message) > _APP_CONTENT_MAX_BYTES:
            raise ValueError(f"message is {_utf8_size(message)} UTF-8 bytes long but the " f"WeCom application limit is {_APP_CONTENT_MAX_BYTES} bytes")

        msgtype = options.get("msgtype") or ("markdown" if message.lstrip().startswith("#") else "text")
        if msgtype not in ("text", "markdown"):
            raise ValueError("send() only supports msgtype 'text'/'markdown'; use send_textcard(), " "send_news(), send_media(), send_template_card() or raw_send() instead")

        return self._dispatch(msgtype, {"content": message}, **options)

    # ------------------------------------------------------------------ #
    # Typed message builders (one thin method per documented message type)
    # ------------------------------------------------------------------ #
    @catch_exception
    def send_text(self, content, **options):
        """Send a ``text`` message (content supports ``\\n`` and ``<a>``).

        Example:
            >>> pusher.send_text("hello <a href=\\"https://a.com\\">x</a>",
            ...                  agentid=1, safe=1)   # doctest: +SKIP
        """

        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be a non-empty string")
        self._ensure_within_bytes(content, _APP_CONTENT_MAX_BYTES, "text content")
        return self._dispatch("text", {"content": content}, **options)

    @catch_exception
    def send_markdown(self, content, **options):
        """Send a ``markdown`` message (<= 2048 UTF-8 bytes).

        Example:
            >>> pusher.send_markdown("# title\\nhello", agentid=1)
            ...                                     # doctest: +SKIP
        """

        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be a non-empty string")
        self._ensure_within_bytes(content, _APP_CONTENT_MAX_BYTES, "markdown content")
        return self._dispatch("markdown", {"content": content}, **options)

    @catch_exception
    def send_textcard(self, title, description, url, btntxt=None, **options):
        """Send a ``textcard`` message.

        Args:
            title: Card title (<= 128 characters, truncated by the server).
            description: Card description (<= 512 characters; supports the
                documented ``gray``/``highlight``/``normal`` div classes).
            url: Click-through URL; must include the http/https scheme.
            btntxt: Optional button text (<= 4 characters, default "详情").

        Example:
            >>> pusher.send_textcard("notice", "ready", "https://a.com",
            ...                      btntxt="查看", agentid=1)  # doctest: +SKIP
        """

        if not title:
            raise ValueError("textcard title is required")
        if not description:
            raise ValueError("textcard description is required")
        if not url:
            raise ValueError("textcard url is required")
        body = {"title": title, "description": description, "url": url}
        if btntxt is not None:
            if len(btntxt) > 4:
                raise ValueError("textcard btntxt must be at most 4 characters")
            body["btntxt"] = btntxt
        return self._dispatch("textcard", body, **options)

    @catch_exception
    def send_news(self, articles, **options):
        """Send a ``news`` message with 1-8 articles.

        Each article is a dict with required ``title`` and ``url`` keys and
        optional ``description`` / ``picurl`` keys. An article may instead
        link to a mini-program with ``appid`` + ``pagepath`` (which then
        replaces ``url``); dicts are forwarded as given after validation.

        Example:
            >>> pusher.send_news([                      # doctest: +SKIP
            ...     {"title": "gift", "url": "https://a.com",
            ...      "picurl": "https://a.com/p.png"},
            ... ], agentid=1)
        """

        if not isinstance(articles, (list, tuple)) or not (1 <= len(articles) <= 8):
            raise ValueError("news requires 1 to 8 articles")
        for index, article in enumerate(articles):
            if not isinstance(article, dict) or not article.get("title"):
                raise ValueError(f"news article #{index} must be a dict with a 'title'")
            if not article.get("url") and not article.get("appid"):
                raise ValueError(f"news article #{index} needs 'url' or 'appid'")
        return self._dispatch("news", {"articles": list(articles)}, **options)

    @catch_exception
    def send_media(self, media_id, msgtype="image", *, title=None, description=None, **options):
        """Send an ``image`` / ``voice`` / ``video`` / ``file`` message.

        Obtain ``media_id`` from :meth:`upload_media`. ``title`` and
        ``description`` only apply to ``video`` messages.

        Example:
            >>> media_id = pusher.upload_media("image", "./chart.png")
            ...                                              # doctest: +SKIP
            >>> pusher.send_media(media_id, "image", agentid=1)
            ...                                              # doctest: +SKIP
        """

        if msgtype not in _MEDIA_MSGTYPES:
            raise ValueError(f"unsupported media msgtype {msgtype!r}; expected one of " f"{sorted(_MEDIA_MSGTYPES)}")
        if not media_id:
            raise ValueError("media_id is required")
        body = {"media_id": media_id}
        if msgtype == "video":
            if title is not None:
                body["title"] = title
            if description is not None:
                body["description"] = description
        return self._dispatch(msgtype, body, **options)

    @catch_exception
    def send_template_card(self, card, **options):
        """Send a ``template_card`` message (card dict built by the caller).

        The full card structures (``text_notice`` / ``news_notice`` / button /
        vote / multiple-choice) are documented at path/90236; build the card
        dict there and pass it in unchanged.

        Example:
            >>> pusher.send_template_card({                # doctest: +SKIP
            ...     "card_type": "text_notice",
            ...     "main_title": {"title": "hi"},
            ...     "card_action": {"type": 1, "url": "https://a.com"},
            ... }, agentid=1)
        """

        if not isinstance(card, dict) or not card.get("card_type"):
            raise ValueError("template card must be a dict with a 'card_type'")
        return self._dispatch("template_card", card, **options)

    @catch_exception
    def upload_media(self, media_type, file):
        """Upload temporary media and return its ``media_id``.

        See https://developer.work.weixin.qq.com/document/path/90253. The
        media id is valid for 3 days. ``file`` may be a path string or an
        open binary file object.

        Args:
            media_type: One of ``"image"`` (JPG/PNG, <=10MB), ``"voice"``
                (AMR, <=2MB, <=60s), ``"video"`` (MP4, <=10MB) or ``"file"``
                (<=20MB).
            file: File path or binary file object.

        Returns:
            The ``media_id`` string on success, or ``None`` on failure.

        Example:
            >>> media_id = pusher.upload_media("file", "./report.zip")
            ...                                              # doctest: +SKIP
        """

        if media_type not in _APP_MEDIA_MAX_BYTES:
            raise ValueError(f"unsupported media_type {media_type!r}; expected one of " f"{sorted(_APP_MEDIA_MAX_BYTES)}")
        filename, raw = _read_source(file)
        limit = _APP_MEDIA_MAX_BYTES[media_type]
        if len(raw) > limit:
            raise ValueError(f"{media_type} is {len(raw)} bytes but the WeCom limit is {limit} bytes")

        token = self.get_access_token()
        if not token:
            raise AccessFailed("failed to obtain access token")
        data = requests.post(
            self.media_upload_url,
            params={"access_token": token, "type": media_type},
            # The multipart field name required by the API is "media".
            files={"media": (filename, raw) if filename else raw},
            timeout=self.timeout,
        ).json()
        _check_errcode(data)
        media_id = data.get("media_id")
        self.success("media id:", media_id)
        return media_id

    # ------------------------------------------------------------------ #
    # Envelope construction and transport
    # ------------------------------------------------------------------ #
    def _dispatch(self, msgtype, body, **options):
        """Build the full envelope for ``msgtype`` and POST it."""

        return self.raw_send(self._build_envelope(msgtype, body, **options))

    def _build_envelope(self, msgtype, body, **options):
        """Assemble a documented application-message envelope.

        Raises:
            ValueError: When ``agentid`` is missing or no receiver can be
                resolved, or when the duplicate-check interval is out of its
                documented [0, 14400] seconds range.
        """

        agentid = options.get("agentid")
        if not agentid:
            raise ValueError("agentid is required for WeCom application messages")

        # touser/toparty/totag must not all be empty; default to @all so a
        # plain composite fan-out call keeps working without options.
        targets = {name: options[name] for name in ("touser", "toparty", "totag") if options.get(name)}
        if not targets:
            targets["touser"] = "@all"

        envelope: dict = {"msgtype": msgtype, "agentid": agentid, **targets, msgtype: body}

        for flag in ("safe", "enable_id_trans", "enable_duplicate_check"):
            value = options.get(flag)
            if value is not None:
                envelope[flag] = int(bool(value)) if flag == "safe" else int(value)
        interval = options.get("duplicate_check_interval")
        if interval is not None:
            interval = int(interval)
            if not 0 <= interval <= 4 * 3600:
                raise ValueError("duplicate_check_interval must be between 0 and 14400 seconds")
            envelope["duplicate_check_interval"] = interval
        return envelope

    @staticmethod
    def _ensure_within_bytes(content, limit, label):
        """Raise ValueError when ``content`` exceeds ``limit`` UTF-8 bytes."""

        size = _utf8_size(content)
        if size > limit:
            raise ValueError(f"{label} is {size} UTF-8 bytes long but the WeCom limit is {limit} bytes")

    @catch_exception
    def raw_send(self, body):
        """POST a fully-built message envelope to the WeCom API.

        Most callers should use :meth:`send` or one of the typed methods;
        this is public so types not covered here (``mpnews``,
        ``miniprogram_notice``, interactive card callbacks) can be sent by
        constructing the envelope manually.

        A response complaining about an invalid/expired access token
        triggers exactly one automatic retry with a force-refreshed token.

        Example:
            >>> pusher.raw_send({"msgtype": "text",   # doctest: +SKIP
            ...                  "agentid": 1000002,
            ...                  "text": {"content": "hi"}})
        """

        token = self.get_access_token()
        if not token:
            raise AccessFailed("failed to obtain access token")
        data = requests.post(self.send_url, params={"access_token": token}, json=body, timeout=self.timeout).json()

        if data.get("errcode") in _TOKEN_INVALID_ERRCODES:
            # Cached token died early: refresh it and retry exactly once.
            self._invalidate_token()
            token = self.get_access_token()
            if not token:
                raise AccessFailed("failed to refresh access token")
            data = requests.post(
                self.send_url,
                params={"access_token": token},
                json=body,
                timeout=self.timeout,
            ).json()

        _check_errcode(data)
        # Note: invaliduser/invalidparty/invalidtag/unlicenseduser may still
        # be present on errcode 0; the delivery succeeded for the rest.
        return self._succeed(raw=data)


@register_channel("workWechatRobot")
class WorkWechatRobot(PushChannel):
    """Send messages through a WeCom group robot webhook ("消息推送").

    The constructor token is the webhook ``key`` query parameter. Supported
    message types: ``text``, ``markdown``, ``markdown_v2``, ``image``,
    ``news``, ``file``, ``voice`` and ``template_card``. Plain ``send()``
    picks text or markdown automatically; the other types use their typed
    methods. Limits (per docs, path/91770):

        - text content <= 2048 UTF-8 bytes; markdown / markdown_v2 <= 4096;
        - image: JPG/PNG only, <= 2MB (base64 + md5 of the raw bytes);
        - news: 1-8 articles, ``title``/``url`` required;
        - uploaded files <= 20MB, voice (AMR) <= 2MB; media_id valid 3 days
          and only usable by the uploading robot;
        - at most 20 messages per minute for one webhook.

    ``text`` and ``markdown`` contents may mention members with the
    ``<@userid>`` syntax (not supported by ``markdown_v2``); text messages
    additionally accept ``mentioned_list`` / ``mentioned_mobile_list``.

    Example:
        Markdown message::

            robot = WorkWechatRobot("your-webhook-key")
            robot.send("# title\\nhello world")

        Text message mentioning everyone::

            robot.send("deploy finished", mentioned_list=["@all"])

        Send a local image and a local file::

            robot.send_image("./chart.png")
            robot.send_local_file("./report.zip")
    """

    base_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook"

    # Documented content and payload limits.
    text_max_bytes = 2048
    markdown_max_bytes = 4096
    image_max_bytes = 2 * _MB
    file_max_bytes = 20 * _MB
    voice_max_bytes = 2 * _MB
    max_articles = 8
    messages_per_minute = 20

    # Send-time options that reach the API.
    allowed_options = frozenset({"msgtype", "mentioned_list", "mentioned_mobile_list"})

    # First bytes that identify JPEG and PNG files.
    _JPEG_MAGIC = b"\xff\xd8\xff"
    _PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

    def __init__(self, token=None, *, timeout=None):
        super().__init__(token, timeout=timeout)
        if not isinstance(token, str) or not token.strip():
            raise ValueError("WorkWechatRobot token must be a non-empty webhook key string")
        # Message-send and media-upload endpoints share the same webhook key.
        self.send_url = f"{self.base_url}/send"
        self.upload_url = f"{self.base_url}/upload_media"

    @catch_exception
    def send(self, message, **options):
        """Send a ``text`` / ``markdown`` / ``markdown_v2`` message.

        ``msgtype`` is auto-detected: a leading ``#`` selects ``markdown``
        unless ``msgtype="markdown_v2"`` is given. Text mention options are
        only attached to ``text`` messages.

        Example:
            >>> robot.send("plain text")                    # doctest: +SKIP
            >>> robot.send("# hi", msgtype="markdown_v2")   # doctest: +SKIP
        """

        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")

        msgtype = options.get("msgtype") or ("markdown" if message.lstrip().startswith("#") else "text")
        if msgtype == "text":
            return self.send_text(
                message,
                mentioned_list=options.get("mentioned_list"),
                mentioned_mobile_list=options.get("mentioned_mobile_list"),
            )
        if msgtype == "markdown":
            return self.send_markdown(message)
        if msgtype == "markdown_v2":
            return self.send_markdown_v2(message)
        raise ValueError("send() msgtype must be 'text', 'markdown' or 'markdown_v2'; use the typed " "send_image()/send_news()/send_file()/send_voice()/send_template_card() " "methods for other types")

    @catch_exception
    def send_text(self, content, mentioned_list=None, mentioned_mobile_list=None):
        """Send a ``text`` message (<= 2048 UTF-8 bytes).

        ``mentioned_list`` / ``mentioned_mobile_list`` accept a list of
        strings or a ``|``-separated string; ``"@all"`` mentions everyone.

        Example:
            >>> robot.send_text("done <@zhangsan>",
            ...                 mentioned_mobile_list=["13800001111"])
            ...                                     # doctest: +SKIP
        """

        self._require_content(content, self.text_max_bytes, "text content")
        body: dict = {"content": content}
        members = _as_member_list(mentioned_list)
        if members is not None:
            body["mentioned_list"] = members
        mobiles = _as_member_list(mentioned_mobile_list)
        if mobiles is not None:
            body["mentioned_mobile_list"] = mobiles
        return self._dispatch("text", body)

    @catch_exception
    def send_markdown(self, content):
        """Send a v1 ``markdown`` message (<= 4096 UTF-8 bytes).

        Supports the documented subset (headings, bold, links, inline code,
        quotes, ``info``/``comment``/``warning`` font colors) and
        ``<@userid>`` mentions in content.

        Example:
            >>> robot.send_markdown('status: <font color="info">ok</font>')
            ...                                     # doctest: +SKIP
        """

        self._require_content(content, self.markdown_max_bytes, "markdown content")
        return self._dispatch("markdown", {"content": content})

    @catch_exception
    def send_markdown_v2(self, content):
        """Send a ``markdown_v2`` message (lists, tables, nested quotes, ...).

        Same 4096-byte limit as v1; note v2 renders as plain text on clients
        older than 4.1.36 and does not support font colors or @ mentions.

        Example:
            >>> robot.send_markdown_v2("| a | b |\\n|---|---|\\n| 1 | 2 |")
            ...                                     # doctest: +SKIP
        """

        self._require_content(content, self.markdown_max_bytes, "markdown_v2 content")
        return self._dispatch("markdown_v2", {"content": content})

    @catch_exception
    def send_image(self, source):
        """Send an ``image`` message from a path, file object or bytes.

        Only JPG and PNG up to 2MB (before base64 encoding) are accepted;
        the image format is checked from its leading magic bytes so a
        renamed file cannot slip through.

        Example:
            >>> robot.send_image("./chart.png")       # doctest: +SKIP
        """

        _, raw = _read_source(source)
        if not raw:
            raise ValueError("image content is empty")
        if len(raw) > self.image_max_bytes:
            raise ValueError(f"image is {len(raw)} bytes but the WeCom robot limit is " f"{self.image_max_bytes} bytes")
        if not (raw.startswith(self._JPEG_MAGIC) or raw.startswith(self._PNG_MAGIC)):
            raise ValueError("robot image messages only support JPG and PNG")

        body = {
            "base64": base64.b64encode(raw).decode("ascii"),
            "md5": hashlib.md5(raw).hexdigest(),
        }
        return self._dispatch("image", body)

    @catch_exception
    def send_news(self, articles):
        """Send a ``news`` message with 1-8 articles.

        Each article needs ``title`` and ``url``; ``description`` and
        ``picurl`` are optional.

        Example:
            >>> robot.send_news([{"title": "gift", "url": "https://a.com"}])
            ...                                     # doctest: +SKIP
        """

        if not isinstance(articles, (list, tuple)) or not (1 <= len(articles) <= self.max_articles):
            raise ValueError(f"news requires 1 to {self.max_articles} articles")
        built = []
        for index, article in enumerate(articles):
            if not isinstance(article, dict):
                raise ValueError(f"news article #{index} must be a dict")
            title = article.get("title")
            url = article.get("url")
            if not title or not url:
                raise ValueError(f"news article #{index} needs non-empty 'title' and 'url'")
            item = {"title": str(title), "url": str(url)}
            if article.get("description"):
                item["description"] = str(article["description"])
            if article.get("picurl"):
                item["picurl"] = str(article["picurl"])
            built.append(item)
        return self._dispatch("news", {"articles": built})

    @catch_exception
    def send_file(self, media_id):
        """Send a ``file`` message using a media id from :meth:`upload`.

        Example:
            >>> media_id = robot.upload("file", "./report.zip")
            ...                                     # doctest: +SKIP
            >>> robot.send_file(media_id)           # doctest: +SKIP
        """

        if not media_id:
            raise ValueError("media_id is required")
        return self._dispatch("file", {"media_id": media_id})

    @catch_exception
    def send_voice(self, media_id):
        """Send a ``voice`` message (AMR media id from :meth:`upload`).

        Example:
            >>> robot.send_voice(robot.upload("voice", "./note.amr"))
            ...                                     # doctest: +SKIP
        """

        if not media_id:
            raise ValueError("media_id is required")
        return self._dispatch("voice", {"media_id": media_id})

    @catch_exception
    def send_template_card(self, card):
        """Send a ``template_card`` message (``text_notice``/``news_notice``).

        Build the card dict per path/91770 and pass it in unchanged.

        Example:
            >>> robot.send_template_card({            # doctest: +SKIP
            ...     "card_type": "text_notice",
            ...     "main_title": {"title": "hi"},
            ...     "card_action": {"type": 1, "url": "https://a.com"},
            ... })
        """

        if not isinstance(card, dict) or not card.get("card_type"):
            raise ValueError("template card must be a dict with a 'card_type'")
        return self._dispatch("template_card", card)

    @catch_exception
    def upload(self, media_type, file):
        """Upload media and return its ``media_id``.

        The id is valid for 3 days and only usable by this robot.
        ``file`` may be a path string or an open binary file object.

        Args:
            media_type: ``"file"`` (ordinary files <= 20MB) or ``"voice"``
                (AMR <= 2MB).
            file: File path or binary file object.

        Returns:
            The ``media_id`` string on success, or ``None`` on failure.

        Example:
            >>> with open("./report.zip", "rb") as fp:    # doctest: +SKIP
            ...     media_id = robot.upload("file", fp)
        """

        if media_type not in ("file", "voice"):
            raise ValueError("robot upload media_type must be 'file' or 'voice'")
        filename, raw = _read_source(file)
        limit = self.file_max_bytes if media_type == "file" else self.voice_max_bytes
        if len(raw) == 0:
            raise ValueError(f"{media_type} content is empty")
        if len(raw) > limit:
            raise ValueError(f"{media_type} is {len(raw)} bytes but the WeCom robot limit is {limit} bytes")

        data = requests.post(
            self.upload_url,
            params={"key": self.token, "type": media_type},
            # The multipart field name required by the API is "media".
            files={"media": (filename, raw) if filename else raw},
            timeout=self.timeout,
        ).json()
        _check_errcode(data)
        media_id = data.get("media_id")
        self.success("media id:", media_id)
        return media_id

    @catch_exception
    def send_local_file(self, path):
        """Upload a local file and immediately send it as a ``file`` message.

        Example:
            >>> robot.send_local_file("./report.zip")   # doctest: +SKIP
        """

        media_id = self.upload("file", path)
        if not media_id:
            return None
        return self.send_file(media_id)

    # ------------------------------------------------------------------ #
    def _dispatch(self, msgtype, body):
        """POST ``{"msgtype": ..., <msgtype>: body}`` to the webhook."""

        return self.raw_send({msgtype: body, "msgtype": msgtype})

    @staticmethod
    def _require_content(content, limit, label):
        """Validate a non-empty string within its documented byte budget."""

        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"{label} must be a non-empty string")
        size = _utf8_size(content)
        if size > limit:
            raise ValueError(f"{label} is {size} UTF-8 bytes long but the WeCom robot limit is {limit} bytes")

    @catch_exception
    def raw_send(self, body):
        """POST a fully-built robot message envelope.

        Example:
            >>> robot.raw_send({"msgtype": "text",   # doctest: +SKIP
            ...                 "text": {"content": "hi"}})
        """

        data = requests.post(self.send_url, params={"key": self.token}, json=body, timeout=self.timeout).json()
        _check_errcode(data)
        return self._succeed(raw=data)
