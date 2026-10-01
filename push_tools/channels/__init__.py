"""Built-in push channels shipped with push-tools.

Importing this package imports every built-in channel module once, which in
turn registers the channel classes on the global registry. Third-party
channels do not live here - they are discovered from installed packages via
the ``push_tools.channels`` entry-point group (see
:mod:`push_tools.registry`).

Example:
    List every available channel name (built-ins + installed plugins)::

        from push_tools import registry
    print(registry.names())
    # ['pushplus', 'qmsg', 'server', 'telegram', 'workWechat',
    #  'workWechatRobot']
"""

from __future__ import annotations

# Importing the modules triggers their @register_channel decorators.
from . import pushplus as pushplus  # noqa: F401
from . import qmsg as qmsg  # noqa: F401
from . import serverchan as serverchan  # noqa: F401
from . import telegram as telegram  # noqa: F401
from . import wechat as wechat  # noqa: F401
