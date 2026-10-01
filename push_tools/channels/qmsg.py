"""Qmsg push channel (API v3).

Service website: https://qmsg.zendee.cn
API reference:  https://qmsg.zendee.cn/docs

Qmsg delivers messages to a QQ account (or a bound QQ group) through a
simple HTTP API authenticated by an API key embedded in the URL path.

API v3 highlights
-----------------
- Endpoints live under the ``/v3/`` prefix.
- Every JSON response carries a boolean ``success`` field; on success the
  ``data`` field holds the *message id*, which can later be polled through
  :meth:`Qmsg.query_status`.
- ``msg`` is required (non-empty, up to :attr:`Qmsg.max_message_length`
  characters); ``group`` optionally targets a bound QQ group number.
- Rate limit: one submission per API key every 5 seconds (0.5s for hosted
  private bots); daily quota: 500 messages (1000 for private bots).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests

from ..base import PushChannel, PushResult
from ..errors import AccessFailed, catch_exception
from ..registry import register_channel

# ---------------------------------------------------------------------- #
# Message delivery status codes returned by /v3/msg/status/{key}
# ---------------------------------------------------------------------- #
#: Message submitted, QQ has not returned a delivery receipt yet.
STATUS_PENDING = 0
#: Message delivered successfully.
STATUS_SENT = 1
#: Message rejected by the platform content-moderation check.
STATUS_VIOLATION = 2
#: Message delivery failed.
STATUS_FAILED = -1

#: Human-readable label for every documented status code.
STATUS_LABELS = {
    STATUS_PENDING: "pending",
    STATUS_SENT: "sent",
    STATUS_VIOLATION: "violation",
    STATUS_FAILED: "failed",
}


@dataclass(frozen=True)
class QmsgStatus:
    """Immutable delivery-state snapshot returned by :meth:`Qmsg.query_status`.

    Attributes:
        msg_id: Message id previously returned by the send API.
        code: Raw status code, one of ``STATUS_PENDING`` (0),
            ``STATUS_SENT`` (1), ``STATUS_VIOLATION`` (2) or
            ``STATUS_FAILED`` (-1).
        label: Lower-case textual form of :attr:`code` (``"unknown"`` when
            the service returns an undocumented code).
        raw: Full decoded JSON response, kept for debugging.

    Example:
        >>> status = qmsg.query_status(42)        # doctest: +SKIP
        >>> status.code                           # doctest: +SKIP
        1
        >>> status.label                          # doctest: +SKIP
        'sent'
    """

    msg_id: int
    code: int
    label: str
    raw: dict


@register_channel("qmsg")
class Qmsg(PushChannel):
    """Deliver messages through the Qmsg API v3.

    Supported ``send()`` options:

        - ``group``: target QQ group number as a string. The group must be
          added and bound in the Qmsg console first; omit it to deliver to
          the QQ account bound to the API key (default single-chat push).

    Unknown options (e.g. ``title=...`` forwarded by a composite fan-out)
    are ignored, so Qmsg can sit next to other channels in one call.

    Example:
        Push to the bound QQ single chat::

            qmsg = Qmsg("your-api-key")
            result = qmsg.send("backup job finished")
            msg_id = result.raw["data"]

        Push to a bound QQ group::

            qmsg.send("deploy finished", group="123456789")

        Poll the asynchronous delivery status (0/1/2/-1)::

            snapshot = qmsg.query_status(msg_id)
            if snapshot.code == STATUS_SENT:
                print("delivered")
    """

    # Base host; every v3 endpoint is derived from it.
    base_url = "https://qmsg.zendee.cn"

    # API version prefix, kept as an attribute so a future v4 migration only
    # touches this one line.
    api_prefix = "/v3"

    # Documented maximum message length in characters.
    max_message_length = 1800

    # Keyword arguments accepted by the send API; everything else in a
    # fan-out call (e.g. ``title=...``) is ignored automatically.
    allowed_options = frozenset({"group"})

    def __init__(self, token=None, *, timeout=None):
        super().__init__(token, timeout=timeout)
        # POST endpoint accepting query/form parameters.
        self.send_url = f"{self.base_url}{self.api_prefix}/send/{self.token}"
        # POST endpoint accepting an ``application/json`` body.
        self.json_send_url = f"{self.base_url}{self.api_prefix}/jsend/{self.token}"
        # GET endpoint reporting asynchronous message delivery status.
        self.status_url = f"{self.base_url}{self.api_prefix}/msg/status/{self.token}"
        # Message id of the most recent successful send (``None`` before any
        # successful call); lets ``query_status()`` be called without args.
        self.last_msg_id = None

    @catch_exception
    def send(self, message, **options):
        # Fail fast on the documented content constraints instead of waiting
        # for the remote service to reject the request.
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")
        if len(message) > self.max_message_length:
            raise ValueError(f"message is {len(message)} characters long but the Qmsg limit " f"is {self.max_message_length} characters")

        # ``msg`` is required; ``group`` is the only documented optional field.
        payload = {"msg": message}
        payload.update(self._filter_options(**options))

        response = requests.post(self.send_url, data=payload, timeout=self.timeout)
        return self._parse_send_response(response.json())

    @catch_exception
    def send_json(self, message, group=None):
        """Send a message against the JSON endpoint ``/v3/jsend/{key}``.

        Functionally identical to :meth:`send` but posts an
        ``application/json`` body, which is convenient when the caller is
        already working with JSON payloads.

        Args:
            message: Non-empty text body (<= 1800 characters).
            group: Optional bound QQ group number.

        Returns:
            A :class:`PushResult` on success, or ``None`` on failure.

        Example:
            >>> qmsg.send_json("hello from JSON")             # doctest: +SKIP
            >>> qmsg.send_json("hello group", group="123")    # doctest: +SKIP
        """

        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")
        if len(message) > self.max_message_length:
            raise ValueError(f"message is {len(message)} characters long but the Qmsg limit " f"is {self.max_message_length} characters")

        body: dict = {"msg": message}
        if group is not None:
            body["group"] = str(group)

        response = requests.post(self.json_send_url, json=body, timeout=self.timeout)
        return self._parse_send_response(response.json())

    def _parse_send_response(self, data: dict) -> PushResult:
        """Validate a v3 send response and cache the returned message id.

        Raises:
            AccessFailed: When the response reports ``success: false``.
        """

        # The docs require judging business success via the ``success`` flag
        # (``code`` is only 0/500 and exists for historical reasons).
        if data.get("success") is True:
            # ``data`` is the asynchronous message id used by query_status().
            self.last_msg_id = data.get("data")
            return self._succeed(raw=data)
        raise AccessFailed(data.get("message"))

    @catch_exception
    def query_status(self, msg_id: "int | None" = None) -> "Optional[QmsgStatus]":
        """Query the asynchronous delivery status of a previously sent message.

        See https://qmsg.zendee.cn/docs -> "消息状态".

        Args:
            msg_id: Message id returned in ``result.raw["data"]`` by
                :meth:`send`. When omitted, the id of the most recent
                successful send on this instance is reused.

        Returns:
            A :class:`QmsgStatus` snapshot on success, or ``None`` on failure.

        Raises:
            ValueError: When no ``msg_id`` is given and no previous send is
                cached on this instance.

        Example:
            >>> result = qmsg.send("hello")                   # doctest: +SKIP
            >>> qmsg.query_status(result.raw["data"]).label   # doctest: +SKIP
            'sent'
            >>> qmsg.query_status()        # reuse last_msg_id  # doctest: +SKIP
        """

        if msg_id is None:
            msg_id = self.last_msg_id
        if msg_id is None:
            raise ValueError("msg_id is required when no successful send has been made yet")

        response = requests.get(self.status_url, params={"msgId": msg_id}, timeout=self.timeout)
        data = response.json()

        if data.get("success") is not True:
            raise AccessFailed(data.get("message"))

        code = data.get("data")
        return QmsgStatus(
            msg_id=int(msg_id),
            code=code,
            label=STATUS_LABELS.get(code, "unknown"),
            raw=data,
        )
