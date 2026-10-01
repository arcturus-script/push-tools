"""Telegram Bot push channel.

Service website: https://core.telegram.org/bots/api
sendMessage reference: https://core.telegram.org/bots/api#sendmessage

A channel delivers text messages through a Telegram bot created with
@BotFather. Authentication uses the bot token issued by BotFather, which is
embedded in the request URL (``/bot<token>/sendMessage``); the target chat is
selected per message with ``chat_id`` (a numeric id, or an ``@channelname``
for public channels/supergroups).

sendMessage highlights
----------------------
- ``text`` is required and must be 1-4096 characters long (after entity
  parsing); longer content must be split by the caller.
- ``parse_mode`` accepts ``"HTML"``, the legacy ``"Markdown"`` and the
  stricter ``"MarkdownV2"`` (V2 requires escaping of ``_*[]()~``>#+-=|{}.!``
  and backtick; HTML needs no escaping of ordinary punctuation).
- Link previews are controlled solely by the ``link_preview_options``
  object (``is_disabled`` / ``url`` / ``prefer_small_media`` /
  ``prefer_large_media`` / ``show_above_text``).
- Broadcast limits: 30 messages/second for free; pass
  ``allow_paid_broadcast=True`` to burst up to 1000 messages/second at 0.1
  Telegram Stars per message. Flood-control rejections return HTTP 429 with
  ``parameters.retry_after`` (seconds to wait).
- A bot cannot open a conversation itself: the user must message the bot
  first (or the bot must be a member of the target group/channel).

This implementation follows Bot API 10.3's ``sendMessage`` parameter list.
"""

from __future__ import annotations

import re

import requests

from ..base import PushChannel, PushResult
from ..errors import AccessFailed, catch_exception
from ..registry import register_channel

# Bot tokens look like "<bot_id>:<auth component>", e.g.
# "123456789:AAEhBOweikSd39..."; the auth component is URL-safe and contains
# letters, digits, '_' or '-'. The check only guards against obvious mistakes
# (empty value, missing colon, whitespace) rather than pinning exact lengths.
_BOT_TOKEN_PATTERN = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{25,}$")

# Documented parse_mode values for sendMessage.
_PARSE_MODES = frozenset({"HTML", "Markdown", "MarkdownV2"})


@register_channel("telegram")
class Telegram(PushChannel):
    """Deliver text messages through the Telegram Bot API (``sendMessage``).

    The constructor token is the bot token from @BotFather. A default
    ``chat_id`` may be given at construction time so the channel can sit in a
    composite fan-out without per-call options; otherwise pass
    ``chat_id=...`` to :meth:`send`.

    Supported ``send()`` options (the documented Bot API 10.3 sendMessage
    fields):

        - ``chat_id``: numeric id (int/str) or ``"@username"``;
        - ``message_thread_id``: forum topic (thread) id;
        - ``direct_messages_topic_id``: direct-messages topic id;
        - ``parse_mode``: ``"HTML"`` / ``"Markdown"`` / ``"MarkdownV2"``;
        - ``entities``: list of MessageEntity dicts (alternative to
          ``parse_mode``, do not combine both);
        - ``link_preview_options``: dict of LinkPreviewOptions fields
          (``is_disabled`` / ``url`` / ``prefer_small_media`` /
          ``prefer_large_media`` / ``show_above_text``);
        - ``disable_notification``: send silently;
        - ``protect_content``: forbid forwarding/saving;
        - ``allow_paid_broadcast``: burst to 1000 msgs/sec at a Stars cost;
        - ``business_connection_id`` / ``message_effect_id``: strings;
        - ``ephemeral_message_parameters`` / ``suggested_post_parameters`` /
          ``reply_parameters`` / ``reply_markup``: JSON-serialized dicts
          forwarded verbatim.

    Unknown options (e.g. ``title=...`` from a composite fan-out) are
    ignored.

    Example:
        Message to a private chat (numeric id obtained from @userinfobot or
        the getUpdates API)::

            pusher = Telegram("123456789:AAEhBO...", chat_id=987654321)
            pusher.send("deploy finished")

        HTML message with no link preview, targeting a public channel::

            pusher.send('<b>alert</b> disk 92%',
                        chat_id="@my_channel", parse_mode="HTML",
                        link_preview_options={"is_disabled": True})

        Silent MarkdownV2 message (remember V2 punctuation escaping)::

            pusher.send("deploy \\_v2\\_ finished", parse_mode="MarkdownV2",
                        disable_notification=True)

        Forum-topic message with an inline keyboard::

            pusher.send("build ok", chat_id=-1001234567890,
                        message_thread_id=42,
                        reply_markup={"inline_keyboard": [[
                            {"text": "open", "url": "https://example.com"}]]})
    """

    # Bot API host; every method hangs off /bot<token>/<method>.
    base_url = "https://api.telegram.org"

    # Documented text length limit for sendMessage (characters, not bytes).
    max_text_length = 4096

    # Keyword arguments accepted by sendMessage; everything else in a
    # fan-out call (e.g. ``title=...``) is ignored automatically.
    allowed_options = frozenset(
        {
            "business_connection_id",
            "chat_id",
            "message_thread_id",
            "direct_messages_topic_id",
            "ephemeral_message_parameters",
            "parse_mode",
            "entities",
            "link_preview_options",
            "disable_notification",
            "protect_content",
            "allow_paid_broadcast",
            "message_effect_id",
            "suggested_post_parameters",
            "reply_parameters",
            "reply_markup",
        }
    )

    def __init__(self, token=None, *, timeout=None, chat_id=None):
        super().__init__(token, timeout=timeout)
        if not isinstance(token, str) or not _BOT_TOKEN_PATTERN.match(token):
            raise ValueError("Telegram token must look like '<bot_id>:<secret>' issued by @BotFather")
        # Default receiver; per-send chat_id overrides it.
        self.default_chat_id = chat_id
        self.send_url = f"{self.base_url}/bot{token}/sendMessage"

    @catch_exception
    def send(self, message, **options):
        """Send a text message via ``POST /bot<token>/sendMessage``.

        Example:
            >>> pusher.send("hello", chat_id=987654321)   # doctest: +SKIP
        """

        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")
        if len(message) > self.max_text_length:
            raise ValueError(f"message is {len(message)} characters long but the Telegram limit " f"is {self.max_text_length} characters")

        body = self._build_body(message, **options)
        response = requests.post(self.send_url, json=body, timeout=self.timeout)
        return self._parse_response(response.json())

    def _build_body(self, message, **options):
        """Assemble the documented sendMessage JSON body.

        Raises:
            ValueError: When no chat id is available, parse_mode is unknown,
            or parse_mode and entities are supplied together.
        """

        chat_id = options.get("chat_id") or self.default_chat_id
        if chat_id is None or (isinstance(chat_id, str) and not chat_id.strip()):
            raise ValueError("chat_id is required (pass it to send() or construct the channel with a default chat_id)")

        parse_mode = options.get("parse_mode")
        if parse_mode is not None and parse_mode not in _PARSE_MODES:
            raise ValueError(f"parse_mode must be one of {sorted(_PARSE_MODES)}, got {parse_mode!r}")
        if parse_mode is not None and options.get("entities") is not None:
            raise ValueError("parse_mode and entities are mutually exclusive")

        body: dict = {"chat_id": chat_id, "text": message}
        for key, value in self._filter_options(**options).items():
            # chat_id already placed; skip None-valued fields so the API
            # applies its own defaults.
            if key == "chat_id" or value is None:
                continue
            body[key] = value
        return body

    def _parse_response(self, data: dict) -> PushResult:
        """Validate a Bot API response envelope.

        Every Bot API method returns ``{"ok": true, "result": ...}`` on
        success and ``{"ok": false, "error_code": N, "description": ...}`` on
        failure. The optional ``parameters`` object (ResponseParameters) may
        carry ``retry_after`` for flood control (HTTP 429) or
        ``migrate_to_chat_id`` when a group became a supergroup.

        Raises:
            AccessFailed: With the error code, description and any
                ResponseParameters hint on failure.
        """

        if data.get("ok") is True:
            return self._succeed(raw=data)

        error_code = data.get("error_code")
        description = data.get("description", "")
        message = f"[{error_code}] {description}".strip() if error_code else description
        parameters = data.get("parameters") or {}
        retry_after = parameters.get("retry_after")
        if retry_after is not None:
            message = f"{message} (retry after {retry_after}s)"
        migrate_to = parameters.get("migrate_to_chat_id")
        if migrate_to is not None:
            message = f"{message} (migrate to chat {migrate_to})"
        raise AccessFailed(message or "Telegram API returned ok=false")
