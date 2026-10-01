"""PushPlus push channel.

Service website: https://www.pushplus.plus
API reference (V1.18, 2026-09-14): https://www.pushplus.plus/doc/guide/api.html
Return codes: https://www.pushplus.plus/doc/guide/code.html
Rate limits: https://www.pushplus.plus/doc/help/limit.html

PushPlus fans messages out to WeChat Official Account, App, webhook robots
(WeCom / DingTalk / Feishu / Bark / ...), mail, SMS, voice and more through
two endpoints authenticated by a user token (or a message token):

- ``POST /send``       - deliver through one channel (``channel``);
- ``POST /batchSend``  - deliver through several channels at once
  (``channel`` / ``option`` are comma-separated parallel lists).

Important behaviour from the docs
---------------------------------
- The API is **asynchronous**: a synchronous ``code == 200`` only means the
  request was accepted. The response ``data`` is a message serial number
  ("shortCode"); use it (or ``callbackUrl``) to learn the final delivery
  result. It must never be interpreted as "message delivered".
- ``template`` defaults to ``html``; supported values are html / txt / json
  / markdown / cloudMonitor / jenkins / route / pay / form / doc / excel.
  ``pushId`` is required for the form / doc / excel templates.
- ``channel`` defaults to ``wechat``; supported values are wechat / app /
  extension / webhook / clawbot / cmcc / qq / cp / mail / sms / voice. The
  webhook / cp / mail / qq channels additionally need an ``option`` channel
  config code created in the PushPlus console.
- ``topic`` (group code) and ``to`` (friend tokens) must not be used
  together; topic takes precedence.
- ``timestamp`` is a millisecond expiry stamp: when the server clock passes
  it, the message is dropped (used to suppress stale notifications).
- Limits (real-name users): 5 requests/minute, 3 identical messages/hour,
  200 wechat requests/day; title <= 100 chars and content <= 20000 chars
  (VIP: 10s/5 requests, 2000/day, title 200, content 100000). Code 900 means
  the account is blocked and callers should stop sending for the day.
"""

from __future__ import annotations

import requests

from ..base import PushChannel, PushResult
from ..errors import AccessFailed, catch_exception
from ..registry import register_channel

# Documented template enum (parameter ``template``).
_TEMPLATES = frozenset(
    {
        "html",
        "txt",
        "json",
        "markdown",
        "cloudMonitor",
        "jenkins",
        "route",
        "pay",
        "form",
        "doc",
        "excel",
    }
)

# Documented channel enum (parameter ``channel``).
_CHANNELS = frozenset(
    {
        "wechat",
        "app",
        "extension",
        "webhook",
        "clawbot",
        "cmcc",
        "qq",
        "cp",
        "mail",
        "sms",
        "voice",
    }
)

# Templates whose content is a stored object referenced by a pushId code.
_PUSHID_REQUIRED_TEMPLATES = frozenset({"form", "doc", "excel"})

# send()/batch_send() options that actually reach the API; everything else
# in a fan-out call (e.g. ``qq=...`` for the Qmsg channel) is ignored.
_DOCUMENTED_OPTIONS = frozenset(
    {
        "title",
        "topic",
        "template",
        "channel",
        "option",
        "callbackUrl",
        "timestamp",
        "to",
        "pre",
        "pushId",
    }
)

# Human-readable meaning of the documented return codes, used only when the
# response does not carry a ``msg`` of its own.
_RETURN_CODES = {
    200: "request accepted",
    302: "not logged in",
    401: "request not authorized (enable the open API feature)",
    403: "request IP not authorized (add it to the open-API whitelist)",
    500: "system error, try again later",
    600: "data error, operation failed",
    805: "permission denied",
    888: "insufficient credits, top-up required",
    900: "account usage restricted (too many requests; stop sending today)",
    903: "invalid user token",
    905: "account has not completed real-name verification",
    999: "server-side validation error (see response body)",
}


@register_channel("pushplus")
class PushPlus(PushChannel):
    """Deliver messages through the PushPlus open API (V1.18).

    Supported ``send()`` options (documented parameters):

        - ``title``: message title (optional);
        - ``template``: content template, defaults to ``html``; a message
          starting with ``#`` is sent as ``markdown`` automatically;
        - ``channel``: delivery channel, defaults to ``wechat``;
        - ``topic``: group code for one-to-many delivery (mutually exclusive
          with ``to``);
        - ``to``: comma-separated friend tokens / WeCom user ids (max 10
          real-name, 100 VIP); mutually exclusive with ``topic``;
        - ``option``: per-channel config code for webhook / cp / mail / qq;
        - ``callbackUrl``: webhook receiving the asynchronous delivery
          result;
        - ``timestamp``: millisecond expiry timestamp (int);
        - ``pre``: member-only preprocessing code;
        - ``pushId``: form/doc/excel object code, required for those
          templates.

    ``webhook=...`` is accepted as a deprecated alias of ``option=...`` for
    callers written against older API versions.

    Example:
        Plain HTML message with a title::

            pusher = PushPlus("your-pushplus-token")
            pusher.send("hello world.", title="greeting")

        Markdown body delivered to a group topic::

            pusher.send("# Hi\\nhello world", title="greeting",
                        template="markdown", topic="ops-group")

        Forward to a pre-configured DingTalk/WeCom webhook robot::

            pusher.send("deploy finished", title="alert",
                        channel="webhook", option="my-dingtalk-code")

        Fan the same message out to several channels at once::

            pusher.batch_send("deploy finished",
                              channels=["wechat", "webhook"],
                              options=[None, "my-dingtalk-code"],
                              title="alert")
    """

    # Single-channel and multi-channel endpoints (HTTPS is supported).
    url = "https://www.pushplus.plus/send"
    batch_url = "https://www.pushplus.plus/batchSend"

    allowed_options = _DOCUMENTED_OPTIONS | {"webhook"}

    def __init__(self, token=None, *, timeout=None):
        super().__init__(token, timeout=timeout)
        if not isinstance(token, str) or not token.strip():
            raise ValueError("PushPlus token must be a non-empty user/message token string")

    @catch_exception
    def send(self, message, **options):
        """Send one message through a single PushPlus channel.

        Example:
            >>> pusher.send("hello world.", title="greeting")
            ...                                              # doctest: +SKIP
        """

        payload = self._build_payload(message, **options)
        data = requests.post(self.url, json=payload, timeout=self.timeout).json()
        return self._parse_response(data)

    @catch_exception
    def batch_send(self, message, channels, *, options=None, **fields):
        """Send one message through several channels via ``/batchSend``.

        Args:
            message: Message content (required).
            channels: Channel list, e.g. ``["wechat", "webhook"]`` or a
                comma-separated string ``"wechat,webhook"``.
            options: Channel config codes aligned with ``channels`` - a list
                of strings/``None`` (``None`` means "no option code",
                rendered as an empty entry), or a ready comma-separated
                string. When given as a list its length must match
                ``channels``.
            **fields: Other documented fields (``title``, ``template``,
                ``topic``, ``to``, ``callbackUrl``, ``timestamp``, ``pre``,
                ``pushId``).

        Returns:
            PushResult whose raw ``data`` is a per-channel result list;
            ``None`` after a logged failure.

        Example:
            >>> pusher.batch_send("disk 92%", ["wechat", "mail"],
            ...                    options=[None, "163"], title="alert")
            ...                                              # doctest: +SKIP
        """

        channel_field, option_field = self._build_batch_fields(channels, options)
        fields["channel"] = channel_field
        if option_field is not None:
            fields["option"] = option_field

        payload = self._build_payload(message, **fields)
        data = requests.post(self.batch_url, json=payload, timeout=self.timeout).json()
        return self._parse_response(data)

    # ------------------------------------------------------------------ #
    # Body construction and validation
    # ------------------------------------------------------------------ #
    def _build_payload(self, message, **options):
        """Assemble the documented JSON request body for either endpoint."""

        if not isinstance(message, str) or not message.strip():
            raise ValueError("content (message) must be a non-empty string")

        # Internal hint used only for template auto-selection, never sent.
        options["_content_lead_hash"] = message.lstrip().startswith("#")
        payload: dict = {"token": self.token, "content": message}
        payload.update(self._normalize_options(**options))
        return payload

    def _normalize_options(self, **options):
        """Validate documented fields and return the API-shaped dict.

        Raises:
            ValueError: On unknown enum values, mutually-exclusive
                topic/to usage, a missing pushId for form/doc/excel, or a
                non-integer timestamp.
        """

        # Legacy alias: the field formerly called "webhook" is now "option".
        if options.get("option") is None and options.get("webhook") is not None:
            options["option"] = options["webhook"]

        # The alias must never be forwarded under its retired name; unset
        # fields are dropped so the server applies its own defaults instead
        # of receiving explicit JSON nulls.
        normalized = {key: value for key, value in self._filter_options(**options).items() if key != "webhook" and value is not None}

        template = normalized.get("template")
        if template is None:
            # Match the convenience behaviour of the other built-in channels:
            # a leading Markdown heading selects the markdown template.
            template = "markdown" if options.get("_content_lead_hash") else "html"
        elif template not in _TEMPLATES:
            raise ValueError(f"unknown template {template!r}; expected one of {sorted(_TEMPLATES)}")
        normalized["template"] = template

        channel = normalized.get("channel")
        if channel is not None:
            # batch_send passes an already-joined comma list; single values
            # are validated against the enum in _build_batch_fields/send.
            single_channels = [part for part in str(channel).split(",") if part]
            if "," not in str(channel):
                if channel not in _CHANNELS:
                    raise ValueError(f"unknown channel {channel!r}; expected one of {sorted(_CHANNELS)}")
            elif any(part not in _CHANNELS for part in single_channels):
                raise ValueError(f"unknown channel in {channel!r}; expected values from " f"{sorted(_CHANNELS)}")

        if normalized.get("topic") and normalized.get("to"):
            raise ValueError("topic and to are mutually exclusive; do not set both")

        if template in _PUSHID_REQUIRED_TEMPLATES and not normalized.get("pushId"):
            raise ValueError(f"pushId is required when template={template!r}")

        timestamp = normalized.get("timestamp")
        if timestamp is not None:
            # Millisecond stamps for the current era have 13 digits
            # (>= 10**12); a 10-digit value is almost certainly seconds.
            if isinstance(timestamp, bool) or not isinstance(timestamp, int):
                raise ValueError("timestamp must be an int of milliseconds, e.g. 1632993318000")
            if timestamp < 1_000_000_000_000:
                raise ValueError("timestamp looks like seconds; PushPlus expects milliseconds " "(multiply by 1000), e.g. 1632993318000")

        return normalized

    @staticmethod
    def _build_batch_fields(channels, options):
        """Serialize the parallel channel / option lists for /batchSend."""

        if isinstance(channels, str):
            channel_list = [part.strip() for part in channels.split(",") if part.strip()]
        elif isinstance(channels, (list, tuple)):
            channel_list = [str(part).strip() for part in channels if str(part).strip()]
        else:
            raise ValueError("channels must be a list/tuple of names or a comma-separated string")
        if not channel_list:
            raise ValueError("at least one channel is required for batch_send")
        unknown = [name for name in channel_list if name not in _CHANNELS]
        if unknown:
            raise ValueError(f"unknown channel(s) {unknown}; expected values from {sorted(_CHANNELS)}")

        option_field = None
        if options is not None:
            if isinstance(options, str):
                option_field = options
            elif isinstance(options, (list, tuple)):
                if len(options) != len(channel_list):
                    raise ValueError(f"options length {len(options)} does not match channels " f"length {len(channel_list)}")
                # Empty/None entries render as empty config codes, matching the
                # documented ",config1," alignment style.
                option_field = ",".join("" if code is None else str(code) for code in options)
            else:
                raise ValueError("options must be a list/tuple aligned with channels or a string")
        return ",".join(channel_list), option_field

    def _parse_response(self, data: dict) -> PushResult:
        """Validate a PushPlus response envelope.

        ``code == 200`` means the server accepted (but has not necessarily
        delivered) the message; any other code is a failure carrying ``msg``.

        Raises:
            AccessFailed: With the code and server message on failure.
        """

        if data.get("code") == 200:
            return self._succeed(raw=data)

        code = data.get("code")
        msg = data.get("msg") or _RETURN_CODES.get(code, "")
        raise AccessFailed(f"[{code}] {msg}".strip() if code else (msg or "PushPlus request failed"))
