"""ServerChan (Server酱) push channel.

Service website: https://sct.ftqq.com
Documentation:   https://sct.ftqq.com/docs/

ServerChan pushes notifications to WeChat (official-account / WeCom),
DingTalk / Feishu groups, Bark, PushDeer or the ServerChan³ App. One HTTP
request delivers a titled, Markdown-capable message.

Two SendKey flavours are supported, and the correct endpoint is selected
automatically from the key prefix (exactly like the official
``serverchan-sdk``):

===========================  ============================================
SendKey                      Endpoint
===========================  ============================================
``SCT...`` (ServerChanTurbo) ``https://sctapi.ftqq.com/{SendKey}.send``
``sctp{uid}t...`` (SC3)      ``https://{uid}.push.ft07.com/send/{key}.send``
===========================  ============================================

Documented constraints
----------------------
- ``title`` is required, must not contain line breaks and is capped at
  :attr:`ServerChan.max_title_length` (32) characters.
- ``desp`` is the optional Markdown body.
- Rate limit: at most 50 requests per minute; the free tier allows 5
  messages per day. Aggregate batch notifications into one message.
"""

from __future__ import annotations

import re
from typing import Optional

import requests

from ..base import PushChannel, PushResult
from ..errors import AccessFailed, catch_exception
from ..registry import register_channel

# Fallback title used when a composite fan-out caller does not provide one.
_DEFAULT_TITLE = "push-tools notification"

# ServerChanTurbo host (keys starting with ``SCT``).
_TURBO_BASE_URL = "https://sctapi.ftqq.com"
# ServerChan³ host template (keys shaped ``sctp{uid}t...``).
_SC3_URL_TEMPLATE = "https://{uid}.push.ft07.com/send/{key}.send"

# Extracts the numeric uid embedded in an SC3 SendKey, e.g.
# ``sctp123tXXXX`` -> ``123``. Mirrors the regex used by the official SDK.
_SC3_UID_PATTERN = re.compile(r"^sctp(\d+)t")


@register_channel("server")
class ServerChan(PushChannel):
    """Deliver messages through the ServerChan API (Turbo SCT or SC3).

    The registered channel name remains ``"server"`` for backward
    compatibility with push-tools 0.0.1.

    Supported ``send()`` options (all optional, see
    https://sct.ftqq.com/docs/getting-started/channels/):

        - ``title``: message title, required by the API but defaulted here
          for fan-out safety; must be one line (<= 32 characters);
        - ``short``: short notification text;
        - ``tags``: tag list for SC3 App grouping;
        - ``channel``: per-request channel number (configured in the Turbo
          console "消息通道" page);
        - ``openid``: extra recipients for the test-account / WeCom-app
          channels (subscriber feature).

    Unknown options (e.g. ``qq``/``group`` for other channels inside a
    composite) are ignored.

    Example:
        A Turbo key and an SC3 key are used identically::

            turbo = ServerChan("SCT-your-turbo-key")
            turbo.send("### report\\nhello world", title="daily report")

            sc3 = ServerChan("sctp123tYourSc3Key")
            sc3.send("hello world", title="hi", tags="deploy")

        Override the delivery channel for one request::

            turbo.send("disk usage 92%", title="alert", channel="9")
    """

    # Documented hard limit for the ``title`` field, in characters.
    max_title_length = 32

    # Keyword arguments accepted by the upstream API; title and desp are
    # handled explicitly and therefore intentionally absent from this set.
    allowed_options = frozenset({"short", "tags", "channel", "openid"})

    def __init__(self, token=None, *, timeout=None):
        super().__init__(token, timeout=timeout)
        # Resolve the endpoint up-front so that a malformed SC3 key fails at
        # construction time rather than on the first send.
        self.send_url, self.kind = self._resolve_endpoint(token)

    @staticmethod
    def _resolve_endpoint(key: "str | None") -> "tuple[str, str]":
        """Return ``(send_url, kind)`` for a Turbo or SC3 SendKey.

        Args:
            key: The SendKey. ``sctp``-prefixed keys are treated as SC3;
                everything else uses the Turbo endpoint.

        Returns:
            A ``(url, kind)`` pair where ``kind`` is ``"sc3"`` or ``"sct"``.

        Raises:
            ValueError: If an ``sctp`` key does not embed a numeric uid in
                the documented ``sctp{uid}t`` shape.

        Example:
            >>> ServerChan._resolve_endpoint("SCTabc")            # doctest: +SKIP
            ('https://sctapi.ftqq.com/SCTabc.send', 'sct')
            >>> ServerChan._resolve_endpoint("sctp123tXYZ")       # doctest: +SKIP
            ('https://123.push.ft07.com/send/sctp123tXYZ.send', 'sc3')
        """

        if isinstance(key, str) and key.startswith("sctp"):
            match = _SC3_UID_PATTERN.match(key)
            if not match:
                raise ValueError("invalid SC3 SendKey: expected the 'sctp{uid}t' shape, " "e.g. 'sctp123tXXXX'")
            uid = match.group(1)
            return _SC3_URL_TEMPLATE.format(uid=uid, key=key), "sc3"

        # Turbo (and any non-SC3 key) uses the classic endpoint.
        return f"{_TURBO_BASE_URL}/{key}.send", "sct"

    def _validate_title(self, title: str) -> str:
        """Validate the documented ``title`` constraints.

        Raises:
            ValueError: If the title is empty, contains a line break or is
                longer than :attr:`max_title_length` characters.
        """

        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        if "\n" in title or "\r" in title:
            raise ValueError("title must not contain line breaks")
        if len(title) > self.max_title_length:
            raise ValueError(f"title is {len(title)} characters long but the ServerChan " f"limit is {self.max_title_length} characters")
        return title

    @catch_exception
    def send(self, message, **options) -> "Optional[PushResult]":
        title = self._validate_title(options.get("title", _DEFAULT_TITLE))

        # JSON body is the encoding recommended by the current official SDK:
        # desp routinely contains Markdown / newlines that are awkward (and
        # length-limited) in a query string.
        body = {"title": title, "desp": message}
        body.update(self._filter_options(**options))

        response = requests.post(
            self.send_url,
            json=body,
            headers={"Content-Type": "application/json;charset=utf-8"},
            timeout=self.timeout,
        )
        return self._parse_response(response.json())

    def _parse_response(self, data: dict) -> PushResult:
        """Validate a ServerChan JSON response.

        Raises:
            AccessFailed: When ``code`` is not ``0``. The modern error
                description lives in ``message``; the legacy ``info`` field
                is accepted as a fallback.
        """

        if data.get("code") == 0:
            return self._succeed(raw=data)
        reason = data.get("message") or data.get("info")
        raise AccessFailed(reason)
