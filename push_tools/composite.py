"""Composite channel: fan one message out to multiple channels.

Implements the composite pattern. Children are kept in insertion order, and a
failure of one child (whether it raises or returns ``None``) never prevents
the remaining children from receiving the message.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, Optional

from .base import PushChannel, PushResult

logger = logging.getLogger("push_tools")


class PushComposite(PushChannel):
    """Aggregate several channels behind the same ``send`` interface.

    Example:
        Fan a message out to PushPlus and Qmsg in one call::

            group = PushComposite()
            group.add("pushplus", create_channel("pushplus", "token-a"))
            group.add("qmsg", create_channel("qmsg", "key-b"))

            results = group.send("hello world", title="greeting", qq="10001")
            # results == {"pushplus": PushResult(...), "qmsg": PushResult(...)}

        Children can also be passed to the constructor or chained::

            group = PushComposite([
                ("pushplus", PushPlus("token-a")),
                ("qmsg", Qmsg("key-b")),
            ]).add("server", ServerChan("key-c"))
    """

    def __init__(
        self,
        children: "Optional[dict | list[tuple]]" = None,
        *,
        timeout: "float | None" = None,
    ):
        super().__init__(token=None, timeout=timeout)
        # Insertion-ordered mapping of child name -> channel instance.
        self._children: Dict[str, PushChannel] = {}
        if children is not None:
            if isinstance(children, dict):
                children = children.items()
            for item in children:
                name, channel = item
                self.add(name, channel)

    # ------------------------------------------------------------------ #
    # Child management
    # ------------------------------------------------------------------ #

    def add(self, name: "str | PushChannel", channel: "PushChannel | None" = None):
        """Attach a child channel.

        Supports two calling styles:

        - ``add("qmsg", Qmsg("key"))`` - explicit lookup name;
        - ``add(Qmsg("key"))`` - use the channel's registered ``name`` (or its
          class name) automatically.

        Returns:
            ``self``, so calls can be chained.

        Raises:
            TypeError: If ``channel`` is not a :class:`PushChannel` instance.
            ValueError: If no unique name could be derived for the child.

        Example:
            >>> group.add("backup-qmsg", Qmsg("key"))   # doctest: +SKIP
            >>> group.add(PushPlus("token"))            # doctest: +SKIP
        """

        if channel is None:
            # Single-argument form: derive the key from the channel itself.
            if not isinstance(name, PushChannel):
                raise TypeError(
                    "add() expects a PushChannel instance when called with one argument"
                )
            channel = name
            name = channel.name or channel.__class__.__name__

        if not isinstance(channel, PushChannel):
            raise TypeError(f"{channel!r} is not a PushChannel instance")

        if not name:
            raise ValueError("a non-empty child name is required")

        self._children[str(name)] = channel
        return self

    def remove(self, name: str):
        """Detach the child registered under ``name``. Missing names are ignored.

        Returns:
            ``self``, so calls can be chained.

        Example:
            >>> group.remove("qmsg")   # doctest: +SKIP
        """

        self._children.pop(name, None)
        return self

    def get(self, name: str) -> "PushChannel | None":
        """Return the child channel registered under ``name``.

        Example:
            >>> group.get("qmsg").send("direct message")   # doctest: +SKIP
        """

        return self._children.get(name)

    def names(self) -> "list[str]":
        """Return the child names in insertion order.

        Example:
            >>> group.names()   # doctest: +SKIP
            ['pushplus', 'qmsg']
        """

        return list(self._children)

    # Convenience container protocol.
    def __contains__(self, name: str) -> bool:
        return name in self._children

    def __iter__(self) -> Iterator[str]:
        return iter(self._children)

    def __len__(self) -> int:
        return len(self._children)

    # ------------------------------------------------------------------ #
    # Delivery
    # ------------------------------------------------------------------ #

    def send(self, message: str, **options: Any) -> "Dict[str, Optional[PushResult]]":
        """Send ``message`` to every child, collecting the results.

        Each child is isolated: if one channel raises (channels are normally
        guarded by ``@catch_exception`` but custom ones may not be), the
        exception is logged and the remaining children still run.

        Args:
            message: Text body delivered to all children.
            **options: Keyword arguments forwarded to every child. Each
                channel ignores options it does not understand.

        Returns:
            Mapping ``{child_name: PushResult | None}`` keyed by child name;
            ``None`` marks a child whose send failed.

        Example:
            >>> results = group.send("hello", title="hi", qq="10001")  # doctest: +SKIP
            >>> {name: result.success for name, result in results.items()}  # doctest: +SKIP
            {'pushplus': True, 'qmsg': True}
        """

        results: Dict[str, Optional[PushResult]] = {}
        for name, child in self._children.items():
            try:
                results[name] = child.send(message, **options)
            except Exception as exc:  # noqa: BLE001 - one child must not block others
                results[name] = None
                logger.error(
                    "[%s] child %r failed > %s: %s",
                    self.label,
                    name,
                    type(exc).__name__,
                    exc,
                )
        return results
