"""Exception hierarchy and error-handling helpers for push-tools.

All exceptions raised by this package derive from :class:`PushToolsError`, so
callers can catch every library failure with a single ``except`` clause.

Example:
    Catch every possible failure in one place::

        from push_tools.errors import PushToolsError

        try:
            pusher.send("hello")
        except PushToolsError as exc:
            print("push failed:", exc)
"""

from __future__ import annotations

import functools
import logging
from typing import Callable, TypeVar

# Single shared logger so applications can configure the verbosity of the
# whole package through ``logging.getLogger("push_tools")``.
logger = logging.getLogger("push_tools")

# Generic type used to preserve the signature of decorated callables.
F = TypeVar("F", bound=Callable)


class PushToolsError(Exception):
    """Base class for *every* exception raised by push-tools."""


class PushChannelError(PushToolsError):
    """Base class for failures reported by a push channel."""


class AccessFailed(PushChannelError):
    """Raised when a remote push service rejects a request.

    The message usually contains the error description returned by the
    upstream HTTP API.

    Example:
        A channel raises this when the remote JSON body indicates failure::

            if data.get("code") != 200:
                raise AccessFailed(data.get("msg"))
    """


class UnknownChannelError(PushToolsError):
    """Raised when no channel class is registered under the requested name.

    Example:
        ::

            try:
                create_channel("does-not-exist")
            except UnknownChannelError as exc:
                print(exc)
    """

    def __init__(self, name: str, available: "list[str] | None" = None):
        self.name = name
        self.available = list(available or [])
        available_text = ", ".join(self.available) or "<none>"
        super().__init__(
            f"Unknown push channel {name!r}. Available channels: {available_text}"
        )


class ChannelAlreadyRegistered(PushToolsError):
    """Raised when a channel name is registered twice without ``override``.

    Example:
        >>> @register_channel("pushplus")  # doctest: +SKIP
        ... class AnotherChannel(PushChannel):
        ...     ...
        ChannelAlreadyRegistered: channel 'pushplus' is already registered
    """


def _target_name(func: Callable, args: tuple) -> str:
    """Return a human-readable label for the object that owns ``func``.

    For bound methods the owning class name is used (mirroring the original
    ``[ClassName]`` log prefix); for plain functions the qualified name of
    the function itself is used.
    """

    if args and hasattr(args[0], "__class__"):
        return args[0].__class__.__name__
    return getattr(func, "__qualname__", func.__name__)


def catch_exception(func: F) -> F:
    """Decorator that logs an exception instead of re-raising it.

    Channels decorated with ``@catch_exception`` never crash the caller:
    network errors, remote API errors and programming errors are logged at
    ``ERROR`` level and the decorated method returns ``None``.

    Returns:
        The wrapped function, which returns the original function's result on
        success, or ``None`` when an exception was caught.

    Example:
        Make a custom channel fault-tolerant::

            class MyChannel(PushChannel):
                @catch_exception
                def send(self, message, **options):
                    requests.post(self.url, data=message, timeout=self.timeout)
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - intentional boundary catch
            logger.error(
                "[%s] An error occurred, because > %s: %s",
                _target_name(func, args),
                type(exc).__name__,
                exc,
            )
            return None

    return wrapper  # type: ignore[return-value]
