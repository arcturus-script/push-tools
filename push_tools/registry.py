"""Channel registry: the plugin backbone of push-tools.

Channels can be added in two ways:

1. **Decorator registration** (built-ins and in-process plugins)::

       from push_tools import PushChannel, register_channel

       @register_channel("bark")
       class Bark(PushChannel):
           def send(self, message, **options):
               ...

2. **Python entry points** (third-party packages installed in the same
   environment). A plugin package declares its channel in ``pyproject.toml``::

       [project.entry-points."push_tools.channels"]
       bark = "push_bark:BarkChannel"

   The class is discovered lazily on the first
   :meth:`ChannelRegistry.get` / :meth:`ChannelRegistry.names` call (or
   eagerly through :func:`load_plugins`).
"""

from __future__ import annotations

import inspect
import logging
import re
from importlib import metadata
from typing import Dict, Optional, Type

from .base import PushChannel
from .errors import ChannelAlreadyRegistered, UnknownChannelError

logger = logging.getLogger("push_tools")

# Entry-point group name used to discover third-party channel plugins.
ENTRY_POINT_GROUP = "push_tools.channels"

# Matches a camel-case boundary so the class name can be turned into a
# default snake_case channel name when no explicit name is provided.
_CAMEL_BOUNDARY_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_BOUNDARY_2 = re.compile(r"([a-z0-9])([A-Z])")


def _camel_to_snake(name: str) -> str:
    """Convert a CamelCase class name into a snake_case channel name.

    Example:
        >>> _camel_to_snake("PushPlus")
        'push_plus'
        >>> _camel_to_snake("WorkWechatRobot")
        'work_wechat_robot'
    """

    snake = _CAMEL_BOUNDARY_1.sub(r"\1_\2", name)
    return _CAMEL_BOUNDARY_2.sub(r"\1_\2", snake).lower()


class ChannelRegistry:
    """Registry mapping channel names to :class:`PushChannel` subclasses.

    The package owns a process-wide singleton named :data:`registry`, but
    applications may create isolated registries for testing.

    Example:
        >>> registry.register("echo", EchoChannel)       # doctest: +SKIP
        >>> registry.get("echo")                          # doctest: +SKIP
        <class '...EchoChannel'>
        >>> registry.is_registered("echo")                # doctest: +SKIP
        True
    """

    def __init__(self):
        self._channels: Dict[str, Type[PushChannel]] = {}
        # Entry points are discovered at most once per registry instance.
        self._entry_points_loaded = False

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register(
        self,
        name: str,
        channel_cls: Type[PushChannel],
        *,
        override: bool = False,
    ) -> Type[PushChannel]:
        """Register a channel class under ``name``.

        Args:
            name: Unique lookup name used by :func:`create_channel`.
            channel_cls: Concrete :class:`PushChannel` subclass.
            override: Set to ``True`` to replace an existing registration.

        Returns:
            The registered class, so this method can be used as a decorator.

        Raises:
            TypeError: If ``channel_cls`` is not a :class:`PushChannel` subclass.
            ChannelAlreadyRegistered: If the name is taken and ``override``
                is ``False``.

        Example:
            >>> registry.register("bark", BarkChannel)           # doctest: +SKIP
            >>> registry.register("bark", BarkV2, override=True) # doctest: +SKIP
        """

        if not inspect.isclass(channel_cls) or not issubclass(
            channel_cls, PushChannel
        ):
            raise TypeError(
                f"{channel_cls!r} must be a subclass of PushChannel to be registered"
            )

        if not override and name in self._channels:
            raise ChannelAlreadyRegistered(
                f"channel {name!r} is already registered to "
                f"{self._channels[name].__name__}"
            )

        self._channels[name] = channel_cls
        # Stamp the class so PushResult / logs can report the registered name.
        channel_cls.name = name
        logger.debug("Registered push channel %r -> %s", name, channel_cls.__name__)
        return channel_cls

    def unregister(self, name: str) -> "Optional[Type[PushChannel]]":
        """Remove a channel registration. Missing names are ignored.

        Example:
            >>> registry.unregister("bark")   # doctest: +SKIP
        """

        return self._channels.pop(name, None)

    def is_registered(self, name: str) -> bool:
        """Return whether a channel is registered under ``name``.

        Example:
            >>> registry.is_registered("pushplus")   # doctest: +SKIP
            True
        """

        return name in self._channels or name in self.names()

    # ------------------------------------------------------------------ #
    # Lookup
    # ------------------------------------------------------------------ #

    def get(self, name: str) -> Type[PushChannel]:
        """Return the channel class registered under ``name``.

        Triggers one-time entry-point discovery so plugins installed after
        process start are still found.

        Raises:
            UnknownChannelError: If the name cannot be resolved.

        Example:
            >>> channel_cls = registry.get("pushplus")
            >>> pusher = channel_cls("your-token")
        """

        channel_cls = self._channels.get(name)
        if channel_cls is None:
            # Give installed plugins a chance before declaring the name unknown.
            self.load_entry_points()
            channel_cls = self._channels.get(name)

        if channel_cls is None:
            raise UnknownChannelError(name, self._channels.keys())
        return channel_cls

    def names(self) -> "list[str]":
        """Return the sorted list of all registered channel names.

        Example:
            >>> registry.names()   # doctest: +SKIP
            ['pushplus', 'qmsg', 'server', 'workWechat', 'workWechatRobot']
        """

        self.load_entry_points()
        return sorted(self._channels)

    def all(self) -> "Dict[str, Type[PushChannel]]":
        """Return a shallow copy of the ``{name: class}`` registration map.

        Example:
            >>> for name, cls in registry.all().items():   # doctest: +SKIP
            ...     print(name, cls)
        """

        self.load_entry_points()
        return dict(self._channels)

    # ------------------------------------------------------------------ #
    # Third-party plugin discovery (PEP 621 entry points)
    # ------------------------------------------------------------------ #

    def load_entry_points(self) -> None:
        """Discover channels exposed by installed packages via entry points.

        Third-party packages declare channels under the
        ``push_tools.channels`` group. Loading happens at most once; repeated
        calls are cheap no-ops. A broken plugin is skipped with a warning so
        it cannot take down the whole registry.

        Example:
            ``pyproject.toml`` of an external plugin package::

                [project.entry-points."push_tools.channels"]
                dingtalk = "push_dingtalk:DingTalkChannel"
        """

        if self._entry_points_loaded:
            return
        self._entry_points_loaded = True

        try:
            entry_points = metadata.entry_points()
            # Python 3.10+ exposes the ``select`` helper; 3.9 returns a dict.
            if hasattr(entry_points, "select"):
                candidates = entry_points.select(group=ENTRY_POINT_GROUP)
            else:  # pragma: no cover - Python 3.9 compatibility branch
                candidates = entry_points.get(ENTRY_POINT_GROUP, [])
        except Exception:  # noqa: BLE001 - discovery must never crash imports
            logger.warning("Failed to scan push-tools entry points", exc_info=True)
            return

        for entry_point in candidates:
            try:
                plugin_cls = entry_point.load()
                self.register(entry_point.name, plugin_cls)
                logger.info(
                    "Loaded push-tools plugin %r from %s",
                    entry_point.name,
                    entry_point.value,
                )
            except ChannelAlreadyRegistered:
                # Built-ins (or an earlier plugin) win; do not shout about it.
                logger.debug(
                    "Plugin %r skipped: channel name already registered",
                    entry_point.name,
                )
            except Exception:  # noqa: BLE001 - isolate a broken plugin
                logger.warning(
                    "Failed to load push-tools plugin %r (%s)",
                    entry_point.name,
                    entry_point.value,
                    exc_info=True,
                )


# Process-wide default registry used by the decorator and the factory.
registry = ChannelRegistry()


def register_channel(
    name: "str | type | None" = None,
    channel_cls: "Type[PushChannel] | None" = None,
    *,
    override: bool = False,
):
    """Register a :class:`PushChannel` subclass on the global :data:`registry`.

    Supports three call styles:

    1. Decorator with an explicit name (recommended)::

           @register_channel("bark")
           class Bark(PushChannel):
               ...

    2. Bare decorator - the name falls back to the class ``name`` attribute
       or its snake_case class name (``BarkChannel`` -> ``bark_channel``)::

           @register_channel
           class BarkChannel(PushChannel):
               ...

    3. Imperative registration, useful for plugins loaded conditionally::

           register_channel("bark", Bark, override=True)

    Args:
        name: Channel lookup name, or the class itself in bare-decorator use.
        channel_cls: Channel class when used as an ordinary function.
        override: Replace an existing registration instead of raising.

    Returns:
        The registered class in imperative/bare use, or a decorator function
        when called as ``@register_channel("name")``.
    """

    def resolve(channel_cls: Type[PushChannel], explicit_name: "str | None") -> str:
        return (
            explicit_name
            or getattr(channel_cls, "name", "")
            or _camel_to_snake(channel_cls.__name__)
        )

    # Bare decorator form: ``@register_channel`` receives the class directly.
    if inspect.isclass(name):
        if channel_cls is not None:
            raise TypeError(
                "register_channel() expects a name string as its first argument"
            )
        resolved = resolve(name, None)
        return registry.register(resolved, name, override=override)

    # Imperative form: ``register_channel("bark", Bark)``.
    if channel_cls is not None:
        return registry.register(name, channel_cls, override=override)

    # Parenthesized decorator form: ``@register_channel("bark")``.
    def decorator(channel_cls: Type[PushChannel]) -> Type[PushChannel]:
        return registry.register(resolve(channel_cls, name), channel_cls, override=override)

    return decorator


def load_plugins() -> None:
    """Eagerly discover third-party entry-point channels.

    Usually unnecessary: discovery runs lazily on the first registry lookup.
    Call this when you want all plugins loaded before listing
    :meth:`registry.names()` at application start-up.

    Example:
        >>> from push_tools import load_plugins, registry
        >>> load_plugins()
        >>> print(registry.names())   # doctest: +SKIP
    """

    registry.load_entry_points()
