"""push-tools: a small, pluggable message-push toolkit.

Public API
----------
Core abstractions:

- :class:`PushChannel` / :class:`PushResult` - channel base class and result.
- :func:`register_channel` - decorator that registers a channel plugin.
- :func:`create_channel` - factory: build a channel by its registered name.
- :class:`PushComposite` - fan one message out to several channels.
- :data:`registry` / :func:`load_plugins` - plugin registry and entry-point
  discovery.

Built-in channels:

- :class:`PushPlus`    (registered name ``"pushplus"``)
- :class:`Qmsg`        (registered name ``"qmsg"``)
- :class:`ServerChan`  (registered name ``"server"``)
- :class:`Telegram`    (registered name ``"telegram"``)
- :class:`WorkWechat`  (registered name ``"workWechat"``)
- :class:`WorkWechatRobot` (registered name ``"workWechatRobot"``)

Quick example::

    import logging
    logging.basicConfig(level=logging.INFO)

    from push_tools import create_channel

    pusher = create_channel("pushplus", "your-token")
    pusher.send("hello world", title="greeting")

Writing a plugin
----------------
Subclass :class:`PushChannel`, decorate it, and start using it::

    from push_tools import PushChannel, register_channel, create_channel

    @register_channel("stdout")
    class StdoutChannel(PushChannel):
        def send(self, message, **options):
            print(message)
            return self._succeed(raw={"echo": message})

    create_channel("stdout").send("hello")

Third-party packages can also ship channels as ``push_tools.channels``
entry points - see :mod:`push_tools.registry`.
"""

from __future__ import annotations

from collections.abc import Mapping

# Core building blocks.
from .base import PushChannel, PushResult
from .composite import PushComposite
from .errors import (
    AccessFailed,
    ChannelAlreadyRegistered,
    PushChannelError,
    PushToolsError,
    UnknownChannelError,
    catch_exception,
)
from .factory import create_channel
from .registry import (
    ENTRY_POINT_GROUP,
    ChannelRegistry,
    load_plugins,
    register_channel,
    registry,
)

# Importing the built-in channel package triggers self-registration.
from . import channels as _channels  # noqa: F401
from .channels.pushplus import PushPlus
from .channels.qmsg import Qmsg
from .channels.serverchan import ServerChan
from .channels.telegram import Telegram
from .channels.wechat import WorkWechat, WorkWechatRobot

__version__ = "0.0.1"

# ---------------------------------------------------------------------- #
# Backward-compatible aliases (push-tools 0.0.1 API)
# ---------------------------------------------------------------------- #
# New code should use the PEP-8 names above; the lowercase aliases exist so
# existing callers keep working unchanged.
push = PushChannel
pushplus = PushPlus
qmsg = Qmsg
server = ServerChan
telegram = Telegram
workWechat = WorkWechat
workWechatRobot = WorkWechatRobot
push_composite = PushComposite


class push_creator:
    """Deprecated factory wrapper from push-tools 0.0.1.

    New code should use :func:`create_channel`, which raises
    :class:`UnknownChannelError` for unknown names instead of printing.

    Example (legacy style)::

        creator = push_creator("qmsg", "your-key")
        creator.send("hello world")
    """

    def __init__(self, type, key):
        self.type = type
        # Preserve the original "print and keep going" behaviour for callers
        # that relied on an unknown type not raising.
        try:
            self.push = self.create(type, key)
        except UnknownChannelError:
            print(f"Unsupported push type: {type}")
            self.push = None

    def create(self, type, key):
        """Build the underlying channel; kept for API compatibility."""

        return create_channel(type, key)

    def send(self, msg, **kwargs):
        """Forward the message to the wrapped channel, if any."""

        if self.push is None:
            print("No push instance created.")
            return None
        return self.push.send(msg, **kwargs)


class _RegistryView(Mapping):
    """Read-only dynamic ``{name: channel_class}`` view of the registry.

    Backward-compatible replacement for the old static ``push_server`` dict:
    it stays in sync with third-party entry-point plugins loaded at runtime.
    """

    def __getitem__(self, name):
        try:
            return registry.get(name)
        except UnknownChannelError as exc:
            raise KeyError(name) from exc

    def __iter__(self):
        return iter(registry.names())

    def __len__(self):
        return len(registry.names())


# Legacy name for the global name -> class mapping.
push_server = _RegistryView()

__all__ = [
    # core
    "PushChannel",
    "PushResult",
    "PushComposite",
    "create_channel",
    "register_channel",
    "registry",
    "ChannelRegistry",
    "load_plugins",
    "ENTRY_POINT_GROUP",
    # errors
    "PushToolsError",
    "PushChannelError",
    "AccessFailed",
    "UnknownChannelError",
    "ChannelAlreadyRegistered",
    "catch_exception",
    # built-in channels
    "PushPlus",
    "Qmsg",
    "ServerChan",
    "Telegram",
    "WorkWechat",
    "WorkWechatRobot",
    # legacy aliases
    "push",
    "pushplus",
    "qmsg",
    "server",
    "telegram",
    "workWechat",
    "workWechatRobot",
    "push_composite",
    "push_creator",
    "push_server",
]
