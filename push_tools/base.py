"""Abstract base class shared by every push channel.

A *channel* is a small adapter that knows how to deliver a text message to
one third-party service (PushPlus, Qmsg, ServerChan, WeCom, ...). Third-party
packages add new services by subclassing :class:`PushChannel` and registering
the subclass with :func:`push_tools.registry.register_channel`.

Example:
    Minimal custom channel::

        from push_tools import PushChannel, register_channel

        @register_channel("stdout")
        class StdoutChannel(PushChannel):
            def send(self, message, **options):
                print(message)
                return self._succeed(raw={"echo": message})
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, Optional

logger = logging.getLogger("push_tools")


@dataclass(frozen=True)
class PushResult:
    """Immutable result object returned by a successful :meth:`PushChannel.send`.

    Attributes:
        success: Always ``True`` for a returned result (``None`` is returned
            on failure by ``@catch_exception``).
        channel: Registered name of the channel that produced the result.
        raw: Parsed JSON body (or any other data) returned by the upstream
            service; useful for debugging and auditing.
        message: Optional human-readable note.

    Example:
        ::

            result = pusher.send("hello")
            result.success   # True
            result.channel   # 'pushplus'
    """

    success: bool
    channel: str
    raw: Any = None
    message: str = ""


class PushChannel(ABC):
    """Abstract base class for all push channels.

    Class attributes:
        name: Registered channel name. Filled in automatically by
            ``@register_channel("...")``; subclasses do not need to set it.
        default_timeout: Default HTTP timeout (seconds) used when the caller
            does not pass ``timeout`` explicitly. Prevents a stalled
            connection from blocking forever.
        allowed_options: White-list of keyword names that
            :meth:`_filter_options` will forward to the upstream API. This
            keeps a fan-out call safe: unknown options are silently ignored.

    Constructor arguments:
        token: Credential required by the service. Most channels take a
            string key/token; the WeCom application channel takes a dict of
            ``{"corpid": ..., "corpSecret": ...}``.
        timeout: Per-request HTTP timeout in seconds; falls back to
            :attr:`default_timeout` when omitted.

    Example:
        Implement a new channel::

            @register_channel("bark")
            class Bark(PushChannel):
                url = "https://api.day.app"
                allowed_options = frozenset({"title", "sound"})

                @catch_exception
                def send(self, message, **options):
                    data = self._filter_options(**options)
                    data["body"] = message
                    res = requests.post(f"{self.url}/{self.token}",
                                        data=data, timeout=self.timeout).json()
                    if res.get("code") == 200:
                        return self._succeed(raw=res)
                    raise AccessFailed(res.get("message"))
    """

    # Filled in by the registry decorator; empty for unregistered subclasses.
    name: ClassVar[str] = ""

    # Network timeout shared by the built-in HTTP channels.
    default_timeout: ClassVar[float] = 10.0

    # Keyword arguments accepted by the upstream API of a concrete channel.
    allowed_options: ClassVar[frozenset] = frozenset()

    def __init__(self, token: Any = None, *, timeout: "float | None" = None):
        # ``token`` is the preferred name; ``key`` is kept as an alias so the
        # original attribute name from push-tools 0.0.1 still works.
        self.token = token
        self.key = token
        self.timeout = self.default_timeout if timeout is None else timeout

    @property
    def label(self) -> str:
        """Log/display label: registered name when available, class name otherwise."""

        return self.name or self.__class__.__name__

    @abstractmethod
    def send(self, message: str, **options: Any) -> "Optional[PushResult]":
        """Send ``message`` to the remote service.

        Args:
            message: Text body to deliver. Channels may accept Markdown / HTML
                depending on their ``msgtype`` / ``template`` options.
            **options: Channel-specific keyword arguments. Unknown keywords
                must be ignored so one :class:`PushComposite` fan-out call can
                carry options for heterogeneous channels.

        Returns:
            A :class:`PushResult` on success, or ``None`` when the method is
            decorated with :func:`~push_tools.errors.catch_exception` and an
            exception was caught.

        Example:
            >>> pusher.send("hello world", title="greeting")  # doctest: +SKIP
        """

        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Helpers reusable by concrete channels
    # ------------------------------------------------------------------ #

    def success(self, *args: Any) -> None:
        """Log an ``INFO`` message prefixed with the channel label.

        Preserved from the original ``push`` base class which printed
        ``[ClassName] Operate successfully.``.

        Example:
            >>> self.success()                                  # doctest: +SKIP
            >>> self.success("media id:", "abc123")             # doctest: +SKIP
        """

        if args:
            logger.info("[%s] %s", self.label, " ".join(str(arg) for arg in args))
        else:
            logger.info("[%s] Operate successfully.", self.label)

    def _succeed(self, raw: Any = None) -> PushResult:
        """Log success and build the :class:`PushResult` returned by ``send``.

        Args:
            raw: Optional raw payload (usually the decoded JSON response).

        Example:
            >>> return self._succeed(raw=response_json)   # doctest: +SKIP
        """

        self.success()
        return PushResult(success=True, channel=self.label, raw=raw)

    def _filter_options(self, **options: Any) -> dict:
        """Keep only keys listed in :attr:`allowed_options`.

        This makes a single ``composite.send(..., title=..., qq=...)`` call
        safe: ``title`` reaches PushPlus while ``qq`` reaches Qmsg and every
        other channel simply ignores the unrelated keys.

        Example:
            ::

                # with allowed_options = frozenset({"title"})
                self._filter_options(title="hi", ignored=1)
                # -> {'title': 'hi'}
        """

        return {
            key: value for key, value in options.items() if key in self.allowed_options
        }
