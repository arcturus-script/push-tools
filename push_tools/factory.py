"""Factory function that builds channel instances from their registered name."""

from __future__ import annotations

from typing import Any, Optional

from .base import PushChannel
from .registry import registry


def create_channel(
    kind: str,
    token: Any = None,
    *,
    timeout: "float | None" = None,
    **options: Any,
) -> PushChannel:
    """Create a channel instance by its registered name.

    Args:
        kind: Registered channel name (see :meth:`registry.names()` for the
            full list, including third-party entry-point plugins).
        token: Service credential (string key, or a credential dict for the
            WeCom application channel).
        timeout: Optional per-request HTTP timeout in seconds.
        **options: Extra keyword arguments forwarded to the channel
            constructor.

    Returns:
        A ready-to-use :class:`PushChannel` instance.

    Raises:
        UnknownChannelError: If ``kind`` is not a registered channel name.

    Example:
        >>> pusher = create_channel("pushplus", "your-token", timeout=5)
        >>> pusher.send("hello", title="greeting")     # doctest: +SKIP

        Plugins registered through entry points are resolved the same way::

        >>> ding = create_channel("dingtalk", "your-dingtalk-webhook")  # doctest: +SKIP
    """

    channel_cls = registry.get(kind)
    constructor_options = dict(options)
    if timeout is not None:
        constructor_options["timeout"] = timeout
    return channel_cls(token, **constructor_options)
